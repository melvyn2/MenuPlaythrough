#!/usr/bin/env python3

#    Copyright (c) 2018 melvyn2
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.


# noinspection PyUnresolvedReferences
from AppKit import NSBezierPath, NSColor, NSImage
# noinspection PyUnresolvedReferences
from Foundation import NSUserDefaults

import rumps
import sounddevice as sd
import json
import sys
import signal


# noinspection PyProtectedMember
class MenuPlaythroughApp(rumps.App):

    def __init__(self):
        super(MenuPlaythroughApp, self).__init__('Menu Playthrough')
        try:
            self.dark = NSUserDefaults.standardUserDefaults()\
                .persistentDomainForName_('NSGlobalDomain')['AppleInterfaceStyle'] == 'Dark'
        except KeyError:
            self.dark = False
        self.devices = [None, None]
        try:
            with self.open('settings.json') as f:
                settings = json.loads(f.read())
                self.devices[0] = settings['in']
                self.devices[1] = settings['out']
                try:
                    sd.default.device[0] = sd.query_devices().index(sd.query_devices(settings['in']))
                except ValueError:
                    self.devices[0] = sd.query_devices()[sd.default.device[0]]['name']
                try:
                    sd.default.device[1] = sd.query_devices().index(sd.query_devices(settings['out']))
                except ValueError:
                    self.devices[1] = sd.query_devices()[sd.default.device[1]]['name']
                self.volume = settings['volume']
                self.started = settings['started']
                self.render_icon = settings['render_icon']
        except FileNotFoundError:
            self.devices[0] = sd.query_devices()[sd.default.device[0]]['name']
            self.devices[1] = sd.query_devices()[sd.default.device[1]]['name']
            self.volume = 1
            self.started = False
            self.render_icon = False
        self.run_show = rumps.MenuItem('Running' if self.started else 'Stopped')
        self.run_show.state = self.started
        self.run_toggle = rumps.MenuItem('    ' + ('Stop' if self.started else 'Start'))
        self.run_toggle.set_callback(self.onoff)
        self.volume_slider = rumps.SliderMenuItem(value=self.volume, max_value=1, dimensions=(150, 22))
        self.volume_slider.set_callback(self.slider)
        self.current_passthrough_volume = [0]
        self.input_devices = rumps.MenuItem('Input')
        self.output_devices = rumps.MenuItem('Output')
        self.refresh_devices()
        self.icon_toggle = rumps.MenuItem('Show activity')
        self.icon_toggle.set_callback(self.toggle_icon)
        self.icon_toggle.state = self.render_icon
        if self.render_icon:
            self.icon_setter()
        else:
            if getattr(sys, 'frozen', False):
                # noinspection PyUnresolvedReferences
                self.icon = sys._MEIPASS[:len(sys._MEIPASS)-5] + 'Resources/icon.png'
            else:
                self.icon = 'imgs/icon.png'
        self.quit_button = None
        self.quit = rumps.MenuItem('Quit')
        self.quit.set_callback(self.exit)
        self.menu = [self.run_show,
                     self.run_toggle,
                     None,
                     'Volume',
                     self.volume_slider,
                     None,
                     self.input_devices,
                     self.output_devices,
                     None,
                     self.icon_toggle,
                     self.quit]
        self.stream = sd.Stream(callback=self.stream_callback)
        sd.set_device_changed_callback(self.full_refresh_devices)
        self.title = None
        if self.started:
            self.started = not self.started
            self.onoff()

    def full_refresh_devices(self):
        sd.refresh_device_list()
        self.refresh_devices()

    def refresh_devices(self):
        try:
            self.input_devices.clear()
        except AttributeError:
            pass
        try:
            self.output_devices.clear()
        except AttributeError:
            pass
        pre_refresh = sd.default
        devlist = sd.query_devices()
        try:
            sd.default.device[0] = devlist.index(sd.query_devices(self.devices[0]))
        except None:
            sd.default.device[0] = sd._lib.Pa_GetDefaultInputDevice()
            self.devices[0] = devlist[sd.default.device[0]]['name']
        try:
            sd.default.device[1] = devlist.index(sd.query_devices(self.devices[1]))
        except None:
            sd.default.device[1] = sd._lib.Pa_GetDefaultInputDevice()
            self.devices[1] = devlist[sd.default.device[1]]['name']
        c = min(sd.query_devices()[sd.default.device[0]]['max_input_channels'],
                sd.query_devices()[sd.default.device[1]]['max_output_channels'])
        sd.default.channels = c, c
        sd.default.samplerate = min(sd.query_devices()[sd.default.device[0]]['default_samplerate'],
                                    sd.query_devices()[sd.default.device[1]]['default_samplerate'])
        for i in devlist:
            if i['max_input_channels'] > 0:
                mi = rumps.MenuItem(i['name'])
                mi.set_callback(self.toggle_input)
                mi.state = devlist[sd.default.device[0]] == i
                self.input_devices.add(mi)
            if i['max_output_channels'] > 0:
                mi = rumps.MenuItem(i['name'])
                mi.set_callback(self.toggle_output)
                mi.state = devlist[sd.default.device[1]] == i
                self.output_devices.add(mi)
        if not pre_refresh == sd.default:
            print('Device settings changed')
            self.reset_stream()

    def reset_stream(self):
        prev_started = self.stream.active
        if prev_started:
            self.stream.stop()
        try:
            self.stream = sd.Stream(callback=self.stream_callback)
            if prev_started:
                self.stream.start()
        except Exception as e:
            rumps.notification('Menu Playthrough', 'Error: Menu Playthrough SoundStream failed to initialize.' +
                               ('The playthrough has been stopped.' if prev_started else ''), e, sound=False)
            self.stream = None

    def save_setting(self):
        with self.open('settings.json', 'w') as f:
            f.write(json.dumps({'in': self.devices[0], 'out': self.devices[1],
                                'volume': self.volume, 'started': self.started, 'render_icon': self.render_icon}))

    def toggle_input(self, sender):
        for i in self.input_devices.values():
            i.state = False
        sd.default.device[0] = sd.query_devices().index(sd.query_devices(sender.title))
        self.devices[0] = sender.title
        sender.state = True
        self.reset_stream()

    def toggle_output(self, sender):
        for i in self.output_devices.values():
            i.state = False
        sd.default.device[1] = sd.query_devices().index(sd.query_devices(sender.title))
        self.devices[1] = sender.title
        sender.state = True
        self.reset_stream()

    def stream_callback(self, indata, outdata, _, time, status):
        if status:
            print('[', time.currentTime, ']', status)
        outdata[:] = indata * self.volume
        if len(self.current_passthrough_volume) > 99:
            self.current_passthrough_volume.pop(0)
        self.current_passthrough_volume.append(abs(round(outdata.mean(), 2)) * 10)

    def exit(self, _=None):
        self.save_setting()
        rumps.quit_application(_)

    def slider(self, sender):
        self.volume = round(sender.value, 2)

    def onoff(self, _=None):
        self.started = not self.started
        if self.stream.active:
            self.stream.stop()
            self.icon_setter()
        elif self.started:
            self.stream.start()
        self.run_show.title = 'Running' if self.started else 'Stopped'
        self.run_show.state = self.started
        self.run_toggle.title = '    ' + ('Stop' if self.started else 'Start')

    def toggle_icon(self, sender):
        sender.state = not sender.state
        self.render_icon = sender.state
        if not sender.state:
            if getattr(sys, 'frozen', False):
                # noinspection PyUnresolvedReferences
                self.icon = sys._MEIPASS[:len(sys._MEIPASS)-5] + 'Resources/icon.png'
            else:
                self.icon = 'imgs/icon.png'

    @rumps.timer(0.5)
    def stream_status_watcher(self, _):
        if self.started and not self.stream.active:
            self.onoff()
            rumps.notification('Menu Playthrough', 'Error: Menu Playthrough SoundStream has crashed.',
                               'The playthrough has stopped.', sound=False)
        self.run_show.title = 'Running' if self.started else 'Stopped'
        self.run_show.state = self.started
        self.run_toggle.title = '    ' + ('Stop' if self.started else 'Start')

    @rumps.timer(0.05)
    def icon_setter(self, _=False):
        if (self.started or not _) and self.render_icon:
            p = (sum(self.current_passthrough_volume) / len(self.current_passthrough_volume) * 2.5) ** 0.25 if _ else 0
            img = NSImage.alloc().initWithSize_((11, 26))
            img.lockFocus()
            fp = NSBezierPath.bezierPathWithRect_(((2, 2), (7, 22)))
            NSColor.darkGrayColor().set()
            fp.fill()
            rp = NSBezierPath.bezierPathWithRect_(((3, 3), (5, p * 20)))
            if p > 0.90:
                NSColor.colorWithRed_green_blue_alpha_((0.5 if self.dark else 1), 0.15, 0.15, 1).set()
            elif p > 0.60:
                NSColor.\
                    colorWithRed_green_blue_alpha_((0.5 if self.dark else 1), (0.5 if self.dark else 0.9), 0, 1).set()
            else:
                NSColor.colorWithRed_green_blue_alpha_(0, (0 if self.dark else 1), (0.5 if self.dark else 0), 1).set()
            rp.fill()
            img.unlockFocus()
            self._icon_nsimage = img
            try:
                self._nsapp.setStatusBarIcon()
            except AttributeError:
                pass


# noinspection PyUnresolvedReferences
app = MenuPlaythroughApp()
for s in [signal.SIGTERM, signal.SIGINT, signal.SIGABRT, signal.SIGIOT, signal.SIGQUIT]:
    signal.signal(s, app.exit)
app.run()
