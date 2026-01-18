import random
import os

def list_voice_segments():
  segments = [
    os.path.splitext (f)[0]
    for f in os.listdir ("voice/" + os.getenv ("VOICE"))
    if f.endswith (".sh")
  ]
  enabled_segments = []
  for segment in segments:
    with open ("voice/" + os.getenv ("VOICE") + "/" + segment + ".sh", "r") as file:
      disabled = False
      for line in file:
        line = line.split ("=")
        if (line[0] == "VOICE_DISABLED"):
          if (int (line[1])):
            disabled = True
      if not disabled:
        enabled_segments += [ segment ]
  return enabled_segments

def load_volumes (segment):
  volume_list = []
  with open ("voice/" + os.getenv ("VOICE") + "/" + segment + ".volume", "r") as file:
    for line in file:
      line = line.split()
      time_ms = float (line[0])
      time_stamp = time_ms / 1000
      volume_list.append ((time_stamp, float (line[1])))
  return volume_list

volumes_dict = dict()
for segment in list_voice_segments():
  volumes_dict[segment] = load_volumes (segment)

def get_closest_index_from_volumes (segment, time_stamp):
  volumes = volumes_dict[segment]
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

def time_to_volume (segment, time_stamp):
  volumes = volumes_dict[segment]
  index = get_closest_index_from_volumes (segment, time_stamp)
  return volumes[index][1]

def time_to_control (segment, time_stamp):
  volumes = volumes_dict[segment]
  return (get_closest_index_from_volumes (segment, time_stamp) / (len (volumes) - 1)) * 2 - 1

if __name__ == "__main__":
  def random_test_diff():
    time = random.uniform (volumes[0][0], volumes[-1][0])
    index = get_closest_index_from_volumes (time)
    index_time = volumes[index][0]
    return time - index_time

  results = [random_test_diff() for _ in range (1000000)]
  step = volumes[1][0] - volumes[0][0]
  print (min (results) * 1000, max (results) * 1000)
  assert (min (results) > -step / 2)
  assert (max (results) < step / 2)
