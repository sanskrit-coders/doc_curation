import math


def equispaced_points_on_circumference(num_points, radius=1, start_angle=0, center=(0, 0)):
  angle_diff = 2 * math.pi / num_points
  points = []

  for i in range(num_points):
    angle = start_angle + i * angle_diff
    x = center[0] + radius * math.cos(angle)
    y = center[1] + radius * math.sin(angle)
    points.append((x, y))

  return points


def point_further_than(p1, p2, t):
  """
  Calculate a point that is farther from P1 than P2 by a factor of t.

  Parameters:
      p1 (tuple): First point (x1, y1)
      p2 (tuple): Second point (x2, y2)
      t (float): Factor

  Returns:
      tuple: Point farther from P1 than P2 by a factor of t (x, y)
  """
  x1, y1 = p1
  x2, y2 = p2

  x = x1 + t * (x2 - x1)
  y = y1 + t * (y2 - y1)

  return (x, y)
