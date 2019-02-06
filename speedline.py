import copy
import datetime
import geopy.distance
import iso8601
import math
import numpy
import sys
import xml
import xml.etree.ElementTree as ET

MT_TIMEZONE = datetime.timezone(datetime.timedelta(days=-1, seconds=61200))

KML_NAMESPACE = "http://www.opengis.net/kml/2.2"

XML_NAMESPACE = "{http://www.topografix.com/GPX/1/1}"

FEET_IN_MILE = 5280

FEET_IN_METERS = 3.28084

ET.register_namespace("", KML_NAMESPACE)
ET.register_namespace("", XML_NAMESPACE)

class Trkseg(object):
  def __init__(self, trkpt_list):
    self.trkpt_list = trkpt_list

  def __str__(self):
    return str(self.__dict__)

class Trkpt(object):
  def __init__(self, lat, lon, ele, time):
    self.lat = lat
    self.lon = lon
    self.ele = ele
    self.time = time

  def __str__(self):
    return str(self.__dict__)

def xmltrkpt_to_instance(xmltrkpt):
  return Trkpt(
    float(xmltrkpt.get("lat")),
    float(xmltrkpt.get("lon")),
    float(xmltrkpt.find(XML_NAMESPACE + "ele").text.strip()),
    iso8601.parse_date(xmltrkpt.find(XML_NAMESPACE + "time").text.strip())
  )

def condensed_trkpt_iter(trkpt_iter, max_feet):
  last_trkpt = next(trkpt_iter)
  yield last_trkpt
  for trkpt in trkpt_iter:
    if calculate_feet_delta(trkpt, last_trkpt) > max_feet:
      yield last_trkpt
      last_trkpt = trkpt

def calculate_feet_delta(trkpt1, trkpt2):
  coords1 = (trkpt1.lat, trkpt1.lon)
  coords2 = (trkpt2.lat, trkpt2.lon)
  horizontal_delta = geopy.distance.distance(coords1, coords2).feet
  vertical_delta = (trkpt1.ele - trkpt2.ele) * FEET_IN_METERS
  return math.sqrt(horizontal_delta ** 2 + vertical_delta ** 2)

def calculate_speed(trkpt1, trkpt2):
  feet_delta = calculate_feet_delta(trkpt1, trkpt2)
  seconds_delta = (trkpt1.time - trkpt2.time).total_seconds()
  try:
    return abs(feet_delta / seconds_delta)
  except ZeroDivisionError:
    return 0

def map_with_look_behind(function, iterable):
  iterable = iter(iterable)
  last_element = next(iterable)
  for i in iterable:
    yield function(i, last_element)
    last_element = i

def grouper(predicate, iterable):
  """ Groups the elements in `iterable` into an iterable of iterables based on the `predicate` """
  iterable = iter(iterable)
  last_element = next(iterable)
  cur_list = [last_element]

  for i in iterable:
    if predicate(i, last_element):
      yield cur_list
      last_element = i
      cur_list = [cur_list[-1]]
    cur_list.append(i)

  yield cur_list


def create_kml_tree(template_filepath, trkpt_list_list, upperbound_speed, lowerbound_speed):
  kml_tree = ET.parse(template_filepath)
  kml_folder = next(kml_tree.iter("{" + KML_NAMESPACE + "}Folder"))
  kml_placemark_template = next(kml_tree.iter("{" + KML_NAMESPACE + "}Placemark"))
  kml_folder.remove(kml_placemark_template)
  for trkpt_list in trkpt_list_list:
    append_kml_coordinates(kml_folder, kml_placemark_template, trkpt_list, upperbound_speed, lowerbound_speed)
  kml_tree.write("new.kml", default_namespace=KML_NAMESPACE)

def map_singular_to_color(singular, singular_max, singular_min):
  max_color = 255
  singular = min(max(singular, singular_min), singular_max)
  red = int((1 - singular / singular_max) * max_color)
  green = int((singular / singular_max) * max_color)
  blue = 0
  alpha = max_color
  return (alpha, blue, green, red)


def append_kml_coordinates(kml_folder, kml_placemark_template, trkpt_list,
                           upperbound_speed, lowerbound_speed):

  kml_placemark = ET.fromstring(ET.tostring(kml_placemark_template))

  kml_coordinates = next(kml_placemark.iter("{" + KML_NAMESPACE + "}coordinates"))
  kml_coordinates.text += "\n".join(map(lambda t: ",".join(map(str, [t.lon, t.lat, t.ele])), trkpt_list))

  average_speed = calculate_speed(trkpt_list[0], trkpt_list[-1])
  color = map_singular_to_color(average_speed, upperbound_speed, lowerbound_speed)
  kml_color = next(kml_placemark.iter("{" + KML_NAMESPACE + "}color"))
  kml_color.text = "".join(map(lambda c: hex(c).replace("0x", "").ljust(2, "0"), color))

  kml_placemark_description = next(kml_placemark.iter("{" + KML_NAMESPACE + "}description"))
  kml_placemark_description.text = " | ".join(
    ("Average speed %.2fmph",
    "Time Delta: %.1fmin",
    "Start Time: %s")) % \
    (round(average_speed / FEET_IN_MILE * 60 * 60, 2),
    abs((trkpt_list[0].time - trkpt_list[-1].time).total_seconds() / 60),
    str(trkpt_list[0].time.astimezone(MT_TIMEZONE)))
  


  kml_folder.append(kml_placemark)


def main():

  xmltrkpt_iter = ET.parse(sys.stdin).getroot().iter(XML_NAMESPACE + "trkpt")

  trkpt_list = list(map(xmltrkpt_to_instance, xmltrkpt_iter))

  trkpt_list_list = list(grouper(lambda trkpt, start_trkpt: calculate_feet_delta(trkpt, start_trkpt) > FEET_IN_MILE / 4, trkpt_list))

  # print(list(map(lambda group: list(map(str, group)), trkpt_list_list)))
  speed_list = list(map_with_look_behind(lambda t, last_t: calculate_speed(t, last_t), trkpt_list))

  upperbound_speed = numpy.percentile(speed_list, 90)
  lowerbound_speed = numpy.percentile(speed_list, 10)

  create_kml_tree("./template.kml", trkpt_list_list, upperbound_speed, lowerbound_speed)


if __name__ == "__main__":
  main()
