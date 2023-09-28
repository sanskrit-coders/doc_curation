import logging
import math
from doc_curation.image.coordinate_geometry import equispaced_points_on_circumference  # Replace with your actual module and function name

def test_points_on_circle():
  num_points = 4
  radius = 5
  center = (0, 0)
  start_angle = 0

  points = equispaced_points_on_circumference(num_points, radius, start_angle, center)
  logging.info(points)
  assert len(points) == num_points

  # Check that the points are approximately on the circle
  for point in points:
    x, y = point
    distance_to_center = math.sqrt((x - center[0]) ** 2 + (y - center[1]) ** 2)
    assert math.isclose(distance_to_center, radius, rel_tol=1e-6)

if __name__ == '__main__':
  test_points_on_circle()
