# Windows check

A hands on check of a Windows build before a release. It takes about 30 minutes. Note anything that
looks wrong with a screenshot and the step number.

## Get the build

1. Push the branch, then open GitHub, Actions, Release, Run workflow, and pick the branch.
2. When the run finishes, download the `package-Windows` artifact and unzip it.
3. If an older Mnemosyn is installed, note its version, then uninstall it from Settings, Apps.

## Install and start

1. Run the installer. Windows SmartScreen may warn because the installer is not signed: choose More
   info, Run anyway. Note whether it warned.
2. The installer, the Start menu entry and the taskbar show the blue key icon, not an old icon.
3. Start Mnemosyn from the Start menu. Time the first window: it should be under about 5 seconds on
   a first start and under about 3 seconds on a second start.
4. Help, About shows the version you expect and opens its links in the browser.

## Display

1. At 100% display scaling, nothing is cut off at the window's starting size.
2. Set Windows display scaling to 125% and then 150% (Settings, System, Display), restart
   Mnemosyn each time, and check: text is sharp, icons are sharp, no labels are cut off, and the 3D
   view fills its area.
3. Make the window narrow (under about 1100 pixels wide) and wide again in each workspace. Panels
   join into tabs when narrow and come back when wide, and nothing overlaps.
4. If you have two monitors with different scaling, drag the window between them. Text and the 3D
   view redraw at the right size.

## Explore and Slices

1. Click a structure in the 3D view: it is outlined, the tree selects it, and Info shows it once
   with its side in the name (no second line saying the side).
2. Narrow the structures panel: long names shorten in the middle, so "(left)" and "(right)" stay
   visible. Hovering shows the full name.
3. Search a structure with Ctrl+F. F frames it, H hides it, I isolates it.
4. In Slices, switch Axial, Coronal and Sagittal, drag the slider, and wheel zoom. Labels follow.
5. Study, Start quiz: the setup dialog has no icons on its buttons and no dark boxes behind its
   labels. Answer two questions, then end the quiz with Esc.
6. Study, Progress: every column of the table can be read without scrolling sideways.

## Pathways

1. Open the Cerebellar motor loop and step with the arrow keys and Space. The route list has no
   names running into each other.
2. Open Thirst and water balance and press Open in the Lab. The Lab opens on Water balance.

## Lab

1. Pick Stress axis, drag Dexamethasone onto the timeline, press Space to play. Playback is smooth
   and the playhead moves steadily.
2. The brain labels do not cover each other. Switch to Circuit with V: no scrollbar, and every
   card's text sits inside its box.
3. Pick Water balance. Add Central diabetes insipidus and the Desmopressin test. Select the test:
   the Inspector shows both urine readings as whole numbers (no "e+").
4. Open the Model tab: every value's setting and unit can be read in the panel. Change one, then
   press its reset button.
5. Save the experiment with Ctrl+S to a folder whose name has a space and a non English letter, for
   example `Mes essais é`. Close it, open it again from File, Open: it opens on Water balance.
6. Undo and redo with Ctrl+Z and Ctrl+Shift+Z.

## Lesion

1. Open Lesion. The outline of a structure selected in Explore is not shown here.
2. Place a lesion By artery (Middle cerebral artery parietal territory, Left). Deficits lists the
   broken routes with one reference list at the end. Hit lists the structures.
3. Paint with Brush on a slice, then erase by dragging with Ctrl held. Undo and redo work.
4. Cases, New case: it says to place a lesion on the Place tab first. Place one and press Check.
5. Leave Lesion for Explore: the earlier selection is outlined again.

## Data and closing

1. Close Mnemosyn and start it again: quiz progress is kept.
2. Uninstall from Settings, Apps. The Start menu entry is gone. Note whether your progress file was
   kept (it lives in your user folder and is meant to stay).
