#!/usr/bin/env python
import sys, os
import pyaudio
import numpy as np
import time
from datetime import datetime


import Tkinter as tk

def incr_lev(incr, lev, minlev, maxlev):
    if incr is None or lev is None:
        return np.random.randint(minlev, maxlev)
    else:
        return np.clip(incr + lev, minlev, maxlev)

class SineWave(object):
    freq0 = 110
    freq_base = 2.0 ** (1.0 / 12.0)
    amp_minlev = -45
    amp_base = 10.0 ** (1.0 / 10.0)

    def incr_freq(self, incr=None):
        self.freq_lev = incr_lev(incr, self.freq_lev, 0, self.freq_maxlev)
        self.freq_next = 2 * np.pi * self.freq0 * self.freq_base ** self.freq_lev

    def incr_amp(self, incr=None):
        self.amp_lev = incr_lev(incr, self.amp_lev, self.amp_minlev, 0)
        self.amp_next = self.amp_base ** self.amp_lev

    def __init__(self, rate=44100, channels=2, record=None):
        self.rate = float(rate)
        self.channels = int(channels)
        self.need_header = False
        if record is not None:
            if not os.path.exists(record):
                self.need_header = True
            self.record_file = open(record, 'a')
        else:
            self.need_header = True
            self.record_file = sys.stdout


        self.freq_maxlev = int(np.floor(
            np.log(self.rate / 2.0 / self.freq0) / np.log(self.freq_base)
        ))
        self.phase = 0.0
        self.samples = 0
        self.freq_lev = self.amp_lev = 0
        self.incr_freq()
        self.incr_amp()
        self.amp = self.amp_next
        self.freq = self.freq_next

    def amp_up(self, *args, **kwargs):
        self.incr_amp(1)

    def amp_down(self, *args, **kwargs):
        self.incr_amp(-1)

    def freq_up(self, *args, **kwargs):
        self.incr_freq(1)

    def freq_down(self, *args, **kwargs):
        self.incr_freq(-1)

    def freq_upoct(self, *args, **kwargs):
        self.incr_freq(12)

    def freq_downoct(self, *args, **kwargs):
        self.incr_freq(-12)

    def append_record(self, *args, **kwargs):
        if self.need_header:
            self.record_file.write('Freq (Hz), Amp (dB), Datetime\n')
            self.need_header = False

        self.record_file.write(
            '%9.2f, %8d, %s\n' % (
                self.freq / (2 * np.pi), 10*np.log10(self.amp),
                datetime.utcnow().isoformat())
        )
        self.record_file.flush()

        # random new amp and freq
        self.incr_freq()
        self.incr_amp()

    def close_record(self):
        if not self.record_file.isatty():
            self.record_file.close()

    def __call__(self, in_data, frame_count, time_info, status):
        t0 = self.samples / self.rate

        if self.freq_next != self.freq:
            self.phase = np.mod(
                self.phase + t0 * (self.freq - self.freq_next), 2 * np.pi )
            self.freq = self.freq_next

        if self.amp_next != self.amp:
            amp = np.linspace(self.amp, self.amp_next, frame_count)
            self.amp = self.amp_next
        else:
            amp = self.amp

        t = t0 + np.arange(frame_count) / self.rate
        data = np.empty((frame_count, self.channels), np.float32)
        data[:,:] = (amp * np.sin(self.phase + self.freq * t))[:,np.newaxis]

        self.samples += frame_count
        return (data.ravel(), pyaudio.paContinue)

class AudioCtx(object):
    def __init__(self, source):
        self.p = pyaudio.PyAudio()
        self.source = source
        self.stream = self.p.open(output=True,
                                  format=pyaudio.paFloat32,
                                  rate=int(self.source.rate),
                                  channels=self.source.channels,
                                  stream_callback=self.source)

    def __enter__(self):
        self.stream.start_stream()
        return self.source

    def __exit__(self ,type, value, traceback):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

def mainloop(source):
    root = tk.Tk()
    frame = tk.Frame(root)
    frame.bind("<Left>", source.freq_down)
    frame.bind("<Right>", source.freq_up)
    frame.bind("<Shift-Left>", source.freq_downoct)
    frame.bind("<Shift-Right>", source.freq_upoct)
    frame.bind("<Up>", source.amp_up)
    frame.bind("<Down>", source.amp_down)
    frame.bind("<space>", source.append_record)
    def quit(c):
        source.close_record()
        root.quit()
    frame.bind("<Escape>", quit)
    frame.pack()
    frame.focus_set()
    root.mainloop()

if __name__ == "__main__":
    try:
        outfile = sys.argv[1]
    except IndexError:
        outfile = None

    with AudioCtx(SineWave(record=outfile)) as source:
        mainloop(source)
