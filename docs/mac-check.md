# Mac check

A hands on check of the Mac build by someone with a Mac. The owner has no Mac, so the Download page
marks the Mac file as not yet checked until this check has passed once. It takes about 30 minutes. Note
anything that looks wrong with a screenshot and the step number, and send the notes back.

On a Mac, use Cmd wherever the app's menus or these steps say Ctrl.

## Before you start

1. Apple menu, About This Mac. Note the chip (it must say Apple M1 or later, not Intel) and the
   macOS version (14 or later).
2. Get `Mnemosyn-<version>-macOS-arm64.dmg` from the link you were sent.

## Install and first open

1. Open the disk image. A window shows Mnemosyn and an Applications folder. Drag Mnemosyn onto
   Applications, then eject the disk image.
2. Open Mnemosyn from Applications or Launchpad. macOS says it could not check the app, because
   this test version is not signed with an Apple certificate. Note the exact words of the message.
3. Close the message. Open System Settings, Privacy & Security, scroll down to the line about
   Mnemosyn and choose Open Anyway, then confirm. Note whether this worked, and whether the choice
   was there at all.
4. Mnemosyn opens. Time the first window: it should be under about 5 seconds on a first start and
   under about 3 seconds on a second start.
5. The Dock and Launchpad show the blue key icon, and it looks right beside other icons (not too
   large, not blurred).
6. Close Mnemosyn and open it again. It opens without any warning this time.

## Menus and window

1. The menu bar at the top of the screen has File, Edit, View, Study, Experiment, Window and Help.
   Note where About Mnemosyn appears (macOS may move it under the Mnemosyn menu).
2. Help, About shows the version you expect and opens its links in the browser.
3. Help, Open data folder opens a folder in Finder. Note its path.
4. Nothing is cut off at the window's starting size. Text and icons are sharp on a Retina screen,
   and the 3D view fills its area and is sharp, not blurred or drawn in one corner.
5. Make the window narrow (under about 1100 points wide) and wide again in each workspace. Panels
   join into tabs when narrow and come back when wide, and nothing overlaps.
6. Use the green button to go full screen and back. The 3D view redraws at the right size.
7. If you have an external monitor, drag the window to it and back.

## Explore and Slices

1. Click a structure in the 3D view: it is outlined, the tree selects it, and Info shows it.
2. Rotate with a drag, zoom with a two finger scroll or pinch on the trackpad, and with a mouse
   wheel if you have one. Note anything that feels reversed or jumpy.
3. Search a structure with Cmd+F. F frames it, H hides it, I isolates it. Note whether H hides the
   structure or hides the whole app (Cmd+H always hides the app on a Mac; plain H should not).
4. In Slices, switch Axial, Coronal and Sagittal, drag the slider, and scroll to zoom. Labels follow.
5. Study, Start quiz: answer two questions, then end the quiz with Esc.
6. Study, Progress: every column of the table can be read without scrolling sideways.

## Pathways, Lab and Lesion

1. Pathways: open the Cerebellar motor loop and step with the arrow keys and Space.
2. Lab: pick Stress axis, drag Dexamethasone onto the timeline, press Space to play. Playback is
   smooth and the playhead moves steadily.
3. Lab: save the experiment with Cmd+S to a folder whose name has a space and a non English
   letter, for example `Mes essais é`. Close it, open it again from File, Open.
4. Undo and redo with Cmd+Z and Cmd+Shift+Z.
5. Lesion: place a lesion By artery (Middle cerebral artery parietal territory, Left). Deficits
   lists the broken routes. Paint with Brush on a slice, then erase by dragging with Cmd held (note
   whether it is Cmd or Ctrl that erases).

## Data and closing

1. Quit with Cmd+Q and open Mnemosyn again: quiz progress and the window layout are kept.
2. Leave Mnemosyn open for a few minutes while you use other apps, then come back: it still
   responds, and the fans or battery do not suggest it is working hard while idle.
3. Drag Mnemosyn from Applications to the Trash. Note whether your progress file was kept (it lives
   in the data folder from Help, Open data folder, and is meant to stay).
