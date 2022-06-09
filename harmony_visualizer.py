import os
import sys
import math
import time
import pygame
import pygame.midi
from pygame.locals import *
import numpy as np

app_title = 'Harmony visualizer'
screen_size = (1920, 1080)
#screen_size = (2560, 1440)
#screen_size = (3840, 2160)
line_width = screen_size[1] // 1081 + 1
bold_line_width = line_width * 3
base_size = screen_size[0] // 240 # 8 pixel in 1920 x 1080
keyboard_margin_x = base_size * 3
key_width = (screen_size[0] - keyboard_margin_x * 2) / 52
keyboard_top = base_size * 100
energy_bottom = keyboard_top - keyboard_margin_x
white_key_width = round(key_width * 33 / 36) #22.5 / 23.5
white_key_height = round(key_width * 150 / 23.5)
black_key_width = round(key_width * 23 / 36) #15 / 23.5
black_key_height = round(key_width * 100 / 23.5)
min_note_no = 21
max_note_no = 109.2 # max spectrum frequency in note no
energy_width = (key_width * 7) / 12 - 2
polar_overtone_radius = screen_size[0] // 10
polar_overtone_center = (polar_overtone_radius + base_size * 7, polar_overtone_radius + base_size * 19)
tone_color = np.array([
    (255, 128, 128),
    (224, 160, 128),
    (192, 192, 128),
    (160, 224, 128),
    (128, 255, 128),
    (128, 224, 160),
    (128, 192, 192),
    (128, 160, 224),
    (128, 128, 255),
    (160, 128, 224),
    (192, 128, 192),
    (224, 128, 160)
], dtype=np.int)

def prepare_midi_ins():
    pygame.midi.init()
    midi_ins = []
    midi_in_info = ''
    for i in range(pygame.midi.get_count()):
        midi_device_info = pygame.midi.get_device_info(i)
        if midi_device_info[2] and not midi_device_info[4]: # is input device and not opened.
            try:
                midi_ins.append(pygame.midi.Input(i))
            except:
                # Failed to open MIDI in
                continue
            if midi_in_info:
                midi_in_info += ' and '
            midi_in_info += '"' + midi_device_info[1].decode('utf-8') + '"'
    if midi_in_info:
        midi_in_info = 'Listening ' + midi_in_info + ' MIDI in(s).'
    else:
        midi_in_info = 'No available MIDI In found.'
    return midi_ins, midi_in_info

def prepare_keyboard():
    keys = []

    class Key:
        pass
    for i in range(128):
        oct = i // 12 - 1
        note = i % 12
        black_key = note in [1, 3, 6, 8, 10]
        x = round(keyboard_margin_x + key_width * (oct * 7 + [0.5, 0.925, 1.5, 2.075, 2.5, 3.5, 3.85, 4.5, 5, 5.5, 6.15, 6.5][note] - 5))
        key= Key()
        key.note_no = i
        key.black_key = black_key
        key.x = x
        key.normalized_x = round(keyboard_margin_x + 0.5 * key_width + (key_width * 7) / 12 * (i - 21))
        key.note_on = False # Whether there is a sound including the damper pedal
        key.key_on = False # Whether the keyboard is pressed
        key.db = 0.0 # Virtual volume in DBs
        key.attack = 0.0 # Whether immediately after the attack. 1.0 indicates that it is just after the attack
        key.harmony = 0.0 # The volume of that harmony in DBs if the pitch is in harmony
        key.display_harmony = 0.0 # Display value with fluctuations added to the volume of the harmony
        keys.append(key)
    return keys

def note_no_to_x(note_no):
    return keyboard_margin_x + 0.5 * key_width + (key_width * 7) / 12 * (note_no - 21) # 1 oct. lower

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def main():
    # initialization
    pygame.init()
    pygame.display.set_icon(pygame.image.load(resource_path('icon_128x128.png')))
    screen = pygame.display.set_mode(screen_size)
    full_screen = False

    pygame.display.set_caption(app_title)

    keyboard = prepare_keyboard()
    damper = False
    midi_ins, midi_in_info = prepare_midi_ins()

    tone_names_font = pygame.font.Font(None, base_size * 5)
    tone_names = ['C', '', 'D', '', 'E', 'F', '', 'G', '', 'A', '', 'B']
    tone_name_sizes = [tone_names_font.size(tone_name) for tone_name in tone_names]
    tone_names = [tone_names_font.render(tone_name, True, tone_color[i]) for i, tone_name in enumerate(tone_names)]

    # main_loop
    font = pygame.font.Font(None, base_size * 4)
    app_title_text = font.render(app_title + '  /  Frieve 2022', True, (255,255,255))
    midi_info_text = font.render(midi_in_info, True, (255,255,255))
    terminated = False
    last_time = time.perf_counter() - 10
    harmony_radius = np.zeros(128)
    mouse_click_note = -1
    while (not terminated):
        current_time = time.perf_counter()
        last_wait_ms = (current_time - last_time) * 1000
        last_time = current_time

        # handle events
        for event in pygame.event.get():
            if event.type == QUIT:
                terminated = True
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    terminated = True
                elif event.key == K_F11:
                    full_screen = not full_screen
                    if full_screen:
                        screen = pygame.display.set_mode(screen_size, FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode(screen_size)
                elif event.key == K_LCTRL or event.key == K_RCTRL:
                    damper = True
            elif event.type == KEYUP:
                if event.key == K_LCTRL or event.key == K_RCTRL:
                    damper = False
            elif event.type == MOUSEBUTTONDOWN and event.button == 1:
                for key in [key for key in keyboard[21:109] if key.black_key]:
                    if event.pos[0] >= key.x - black_key_width / 2 and event.pos[0] < key.x + black_key_width / 2 and event.pos[1] >= keyboard_top and event.pos[1] < keyboard_top + black_key_height:
                        mouse_click_note = key.note_no
                if mouse_click_note < 0:
                    for key in [key for key in keyboard[21:109] if not key.black_key]:
                        if event.pos[0] >= key.x - white_key_width / 2 and event.pos[0] < key.x + white_key_width / 2 and event.pos[1] >= keyboard_top and event.pos[1] < keyboard_top + white_key_height:
                            mouse_click_note = key.note_no
                if mouse_click_note >= 0:
                    keyboard[mouse_click_note].key_on = True
                    keyboard[mouse_click_note].attack = 1.0
                    keyboard[mouse_click_note].db = 96.0

            elif event.type == MOUSEBUTTONUP and event.button == 1:
                keyboard[mouse_click_note].key_on = False    
                mouse_click_note = -1

        # midi in
        for midi_in in midi_ins:
            if midi_in.poll():
                midi_events = midi_in.read(88)
                for midi_event in midi_events:
                    if midi_event[0][0] % 16 != 9: # ignore ch 10
                        midi_event_type = midi_event[0][0] // 16

                        if midi_event_type == 9: # note on
                            keyboard[midi_event[0][1]].key_on = True
                            keyboard[midi_event[0][1]].attack = 1.0
                            keyboard[midi_event[0][1]].db = max(math.log(midi_event[0][2] / 127) / math.log(2.0) * 6.0 + 96.0, keyboard[midi_event[0][1]].db)
                        elif midi_event_type == 8: # note off
                            keyboard[midi_event[0][1]].key_on = False
                        elif midi_event_type == 11:
                            cc_no = midi_event[0][1]
                            if cc_no == 64: # damper
                                damper = midi_event[0][2] > 0
                        # print(midi_event)

        # update keyboard status
        overtone_list = []
        harmony_buf = [[] for i in range(128)]
        harmony_list = []
        for key in keyboard:
            key.harmony = 0.0 # reset harmony volume
        for key in keyboard:
            key.note_on = key.key_on or (key.note_on and damper)
            key.db -= last_wait_ms * (0.003 if key.note_on else 0.024)
            if key.db < 0.0:
                key.db = 0
            else:
                processed_note_no = [] 
                for overtone_index in range(1, 384):
                    energy = key.db - math.log(overtone_index) / math.log(2.0) * 3.0
                    freq = key.note_no + math.log(overtone_index) / math.log(2.0) * 12
                    if freq < min_note_no or energy < 60.0 or freq >= max_note_no:
                        break
                    overtone_list.append([key.note_no, freq, energy, key.attack])

                    if overtone_index <= 10:
                        overtone_note_no = int(round(freq))
                        octave = overtone_index & (overtone_index - 1) == 0
                        for harmony_note_no, harmony_overtone_index in harmony_buf[overtone_note_no]:
                            harmony_octave = harmony_overtone_index & (harmony_overtone_index - 1) == 0 
                            if key.note_no % 12 != harmony_note_no % 12 and harmony_note_no not in processed_note_no and (not octave or not harmony_octave):# ignore octave
                                brightness = min(key.db, keyboard[harmony_note_no].db) - 60
                                keyboard[overtone_note_no].harmony = max(brightness, keyboard[overtone_note_no].harmony)
                                if overtone_index > 1:
                                    harmony_list.append([key.note_no, overtone_index, brightness])
                                if harmony_overtone_index > 1:
                                    harmony_list.append([harmony_note_no, harmony_overtone_index, brightness])
                                processed_note_no.append(harmony_note_no)
                        harmony_buf[overtone_note_no].append([key.note_no, overtone_index])

            key.attack = max(key.attack - last_wait_ms * 0.02, 0.0)
        overtone_list.sort(key = lambda x: x[2]) # sort with energy
        harmony_list.sort(key = lambda x: x[2]) # sort with brightness

        # fill screen
        screen.fill((0,0,0))

        # draw white keybed
        for key in [key for key in keyboard[21:109] if not key.black_key]:
            screen.fill((255, 255, 255) if not key.note_on else tone_color[key.note_no % 12], Rect(key.x - white_key_width // 2, keyboard_top, white_key_width, white_key_height - (base_size // 3 if key.attack > 0.0 else 0)))
        # draw black keybed
        for key in [key for key in keyboard[21:109] if key.black_key]:
            screen.fill((0, 0, 0), Rect(key.x - black_key_width // 2, keyboard_top, black_key_width, black_key_height))
            if key.note_on:
                screen.fill(tone_color[key.note_no % 12], Rect(key.x - black_key_width / 2 + line_width, keyboard_top, black_key_width - line_width * 2, black_key_height - line_width - (base_size // 3 if key.attack > 0.0 else 0)))

        # draw harmony volume
        for key in keyboard[21:109]:
            key.display_harmony = key.display_harmony * 0.05 + ((key.harmony + np.random.randn() * 6)* 0.95 if key.harmony > 0.0 else 0.0)
            if key.display_harmony > base_size:
                pygame.draw.circle(screen, (160, 160, 160), (key.normalized_x + 1, energy_bottom + 1), key.display_harmony * base_size / 24, line_width * 2)

        # draw harmony
        for i, (note_no, overtone_index, brightness) in enumerate(harmony_list):
            x1 = note_no_to_x(note_no)
            overtone_note_no = note_no + math.log(overtone_index) / math.log(2.0) * 12
            x2 = note_no_to_x(overtone_note_no)
            height = base_size * 4 + math.log(overtone_index) / math.log(2.0) * base_size * 20
            color = (tone_color[note_no % 12] * brightness / 36).astype(np.int)

            point = []
            resolution = int(x2 - x1) // 6
            for i in range(resolution + 1):
                point.append((x1 + (x2 - x1) * i / resolution, energy_bottom - math.sqrt(math.sin(i / resolution * 3.1415926)) * height))
            pygame.draw.lines(screen, color, False, point, line_width)

            # draw overtone_index
            if i >= len(harmony_list) - 16:
                overtone_text = font.render(str(overtone_index), True, color)
                overtone_text_size = font.size(str(overtone_index))
                screen.blit(overtone_text, [(x1 + x2 - overtone_text_size[0]) // 2, energy_bottom - height - overtone_text_size[0] - base_size * 2])

        # draw overtone (linear)
        for note_no, freq, energy, attack in overtone_list:
            height = (energy - 60.0) * base_size
            x = note_no_to_x(freq)
            pygame.draw.line(screen, tone_color[note_no % 12], (x, energy_bottom - height), (x, energy_bottom), bold_line_width if attack > 0 else line_width)

        # draw key center dot
        for key in keyboard[21:109]:
            pygame.draw.circle(screen, (255, 255, 255), (key.normalized_x + 1, energy_bottom + 1), (3 * base_size) // 8, 0)

        # draw overtone (polar)
        for i in range(6):
            x = math.sin(i / 12 * math.pi * 2.0) * polar_overtone_radius
            y = math.cos(i / 12 * math.pi * 2.0) * polar_overtone_radius
            pygame.draw.line(screen, (64, 64, 64), (polar_overtone_center[0] + x, polar_overtone_center[1] - y), (polar_overtone_center[0] - x, polar_overtone_center[1] + y), line_width)
        pygame.draw.circle(screen, (96, 96, 96), polar_overtone_center, polar_overtone_radius, line_width)
        for i in range(12):
            x = math.sin(i / 12 * math.pi * 2.0) * (polar_overtone_radius + base_size * 3)
            y = math.cos(i / 12 * math.pi * 2.0) * (polar_overtone_radius + base_size * 3)
            screen.blit(tone_names[i], [polar_overtone_center[0] + x - tone_name_sizes[i][0] / 2, polar_overtone_center[1] - y - tone_name_sizes[i][0] / 2])
        for note_no, freq, energy, attack in overtone_list:
            r = (freq - 24) / (max_note_no - 24) * polar_overtone_radius
            angle = freq / 12
            pos = (polar_overtone_center[0] + math.sin(angle * math.pi * 2.0) * r + 1, polar_overtone_center[1] - math.cos(angle * math.pi * 2.0) * r + 1)
            if r > 0.0:
                radius = ((energy / 8 - 7 + attack * 2) * base_size) // 8
                if radius > 1:
                    pygame.draw.circle(screen, tone_color[note_no % 12], pos, radius, 0)
                else:
                    screen.set_at((int(pos[0]), int(pos[1])), tone_color[note_no % 12])

        # display info
        screen.blit(app_title_text, [keyboard_margin_x, keyboard_margin_x])
        screen.blit(midi_info_text, [keyboard_margin_x, keyboard_margin_x // 2 * 5])

        # draw
        pygame.display.update()

        # wait
        pygame.time.wait(10)

    for midi_in in midi_ins:
        midi_in.close()
    pygame.midi.quit()
    pygame.quit()


if __name__ == "__main__":
    main()