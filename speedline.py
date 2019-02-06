import copy
import xml
import numpy
import geopy.distance
import iso8601
import datetime
import sys
import xml.etree.ElementTree as ET

KML_NAMESPACE = "http://www.opengis.net/kml/2.2"

XML_NAMESPACE = "{http://www.topografix.com/GPX/1/1}"

FEET_IN_MILE = 5280

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
  return geopy.distance.distance(coords1, coords2).feet

def calculate_speed(trkpt1, trkpt2):
  feet_delta = calculate_feet_delta(trkpt1, trkpt2)
  seconds_delta = (trkpt1.time - trkpt2.time).total_seconds()
  try:
    return feet_delta / seconds_delta
  except ZeroDivisionError:
    return 0

def map_with_look_behind(function, iterable):
  last_element = next(iterable)
  yield last_element
  for i in iterable:
    function(i, last_element)
    last_element = i
    yield last_element

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


def create_kml_tree(template_filepath, trkpt_iter_iter):
  kml_tree = ET.parse(template_filepath)
  kml_folder = next(kml_tree.iter("{" + KML_NAMESPACE + "}Folder"))
  kml_placemark_template = next(kml_tree.iter("{" + KML_NAMESPACE + "}Placemark"))
  kml_folder.remove(kml_placemark_template)
  for trkpt_iter in trkpt_iter_iter:
    append_kml_coordinates(kml_folder, kml_placemark_template, trkpt_iter)
  kml_tree.write("new.kml", default_namespace=KML_NAMESPACE)


def append_kml_coordinates(kml_folder, kml_placemark_template, trkpt_iter):
  kml_placemark = ET.fromstring(ET.tostring(kml_placemark_template))

  kml_coordinates = next(kml_placemark.iter("{" + KML_NAMESPACE + "}coordinates"))
  kml_coordinates.text += "\n".join(map(lambda t: ",".join(map(str, [t.lon, t.lat, t.ele])), trkpt_iter))

  kml_folder.append(kml_placemark)


def main():

  xmltrkpt_iter = ET.parse(sys.stdin).getroot().iter(XML_NAMESPACE + "trkpt")

  trkpt_iter = map(xmltrkpt_to_instance, xmltrkpt_iter)

  trkpt_iter_iter = grouper(lambda trkpt, start_trkpt: calculate_feet_delta(trkpt, start_trkpt) > FEET_IN_MILE / 4, trkpt_iter)

  # print(list(map(lambda group: list(map(str, group)), trkpt_iter_iter)))

  create_kml_tree("./template.kml", trkpt_iter_iter)


if __name__ == "__main__":
  main()
