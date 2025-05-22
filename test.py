import sounddevice as sd
for idx, d in enumerate(sd.query_devices()):
    print(idx, d['name'])
