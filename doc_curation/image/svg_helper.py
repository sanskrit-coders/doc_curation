import math

from doc_curation.image import coordinate_geometry

def mark_equispaced_points_on_circumference(num_points, radius=1, start_angle=0, center=(500, 500)):
  points = coordinate_geometry.equispaced_points_on_circumference(num_points=num_points, radius=radius, start_angle=start_angle, center=center)
  for point in points:
    print(f'<circle cx="{point[0]}" cy="{point[1]}" r="3" fill="red" />')
    

def get_quadratic_beizier_petal(p1, p2, center, end_thickness_factor=0.25):
  factor = abs(math.dist(p2, center) - math.dist(p1, center))/math.dist(p1, center)*end_thickness_factor + 1
  p = coordinate_geometry.point_further_than(p1=center, p2=p1, t=factor)
  return f'<path d="M {p1[0]},{p1[1]} Q {p[0]},{p[1]} {p2[0]},{p2[1]}" fill="none" stroke="blue" stroke-width="2" />'


def mandala_petals(inner_radius, outer_radius, num_petals, start_angle=0, center=(500, 500), end_thickness_factor=0.25):
  inner_points = coordinate_geometry.equispaced_points_on_circumference(num_points=num_petals*2, radius=inner_radius, start_angle=start_angle, center=center)
  outer_points = coordinate_geometry.equispaced_points_on_circumference(num_points=num_petals, radius=outer_radius, start_angle=start_angle, center=center)
  for index in range(num_petals):
    p_mid = outer_points[index]
    p_next = inner_points[index * 2 + 1]
    p_prev = inner_points[index * 2 - 1 % len(inner_points)]
    print(get_quadratic_beizier_petal(p_prev, p_mid, center=center, end_thickness_factor=end_thickness_factor))
    print(get_quadratic_beizier_petal(p_next, p_mid, center=center, end_thickness_factor=end_thickness_factor))


if __name__ == '__main__':
  pass
  # mark_equispaced_points_on_circumference(num_points=16, start_angle=math.pi/2, radius=121.24)
  # mandala_petals(num_petals=8, start_angle=math.pi/2, inner_radius=121.24, outer_radius=191, end_thickness_factor=0.75)
  mandala_petals(num_petals=8, start_angle=math.pi/2, inner_radius=226, outer_radius=295, end_thickness_factor=0.5)
  mandala_petals(num_petals=16, start_angle=math.pi/2, inner_radius=295, outer_radius=365, end_thickness_factor=0.5)  