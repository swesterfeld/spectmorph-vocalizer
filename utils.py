def load_volumes():
  volume_list = []
  with open ("voice/sven.volume", "r") as file:
    for line in file:
      line = line.split()
      time_ms = float (line[0])
      time_stamp = time_ms / 1000
      volume_list.append ((time_stamp, float (line[1])))
  return volume_list

volumes = load_volumes()

def get_closest_index_from_volumes (time_stamp):
  t0 = volumes[0][0]
  t1 = volumes[-1][0]
  n = len (volumes)

  if n < 2:
    raise RuntimeError ("volume list must contain least 2 elements")

  # compute time stamp distance between adjacent frames (AKA frame_step)
  dt = (t1 - t0) / (n - 1)

  # compute closest frame index
  index = round ((time_stamp - t0) / dt)
  return max (0, min (index, n - 1))

def time_to_volume (time_stamp):
  index = get_closest_index_from_volumes (time_stamp)
  return volumes[index][1]

def time_to_control (time_stamp):
  return (get_closest_index_from_volumes (time_stamp) / (len (volumes) - 1)) * 2 - 1
