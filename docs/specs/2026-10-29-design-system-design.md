# Design system and interface redesign

Date: 2026-10-29
Status: approved by the owner on 2026-10-29
Mockups: `.superpowers/brainstorm/940189-1793263360/content/` (`foundations.html`, `dark-variants.html`, `tab-styles.html`, `lab-screen.html`; not committed). `lab-screen.html` is the reference screen.

## 1. Why

The owner tested the app and found it works but looks primitive and chunky: charts squashed at the bottom of the Lab, panels that appear twice, plain text buttons, and no consistent sizes. People will use Mnemosyn, so it must feel clean, well made and familiar, and be free of layout bugs. The owner does not want to copy another program: the design comes from what is known to make interfaces readable and usable, made to fit Mnemosyn, and applied to the whole app.

A capture of every workspace at a narrow window (850 px wide, a real case on the owner's machine) found these bugs, which this project fixes:

1. Stray tab bars: the Lab's hidden Timeline and Charts docks leave a tab bar ("Ti…", "Ch…") over the top left of the menu bar in every workspace; the Structures and Pathways tab bar is drawn two or three times, once over the Activity chart.
2. The 3D view is squeezed to about 70 px between the side panels in Explore, Pathways and the Lab; the centre has no minimum size.
3. Lab charts: four stacked plots each about 60 px tall, the time axis repeated under every plot, rotated value labels cut off, and the adrenal plot reading about 900 because the chart library adds a "milli" prefix to the axis (the value is 0.87 to 0.91).
4. The Activity chart's legend lies over its lines and its axis label is cut to "ve level".
5. Experiment names and panel tabs are cut ("Remove th…", "Experi…", "Mo…").
6. The toolbar is plain text buttons with key hints ("Hide (H)"); the Lab's toolbar overflows into a ».
7. The circuit view uses tiny text in small boxes with large empty space around them.
8. The Lab's strip of parts outside the brain shows as loose text at the top of the 3D view.
9. The Info panel's title wraps badly and the disclaimer is bright red text.
10. Sizes vary everywhere: buttons, headings, spacing and padding have no shared values.

## 2. Goals, what it is not, what would make it fail

Goals:

1. One design system defined in one place in the code (colours, type, spacing, sizes, corners, icons) that every view uses; no colour, font size or spacing value is written anywhere else.
2. Every workspace, panel, dialog, chart and the 3D view restyled on it, so the app looks like one product.
3. Every bug in section 1 fixed, each with a test so it cannot come back.
4. The app looks the same on every computer: the font and icons ship inside the app.
5. It still works and looks right at a narrow window (850 px wide) and at a large one (2560 px).

Not goals:

1. A light theme. Mnemosyn stays dark only for now (owner's decision); the design must not block adding one later.
2. New features. Behaviour stays as it is unless a change is named in this document.
3. Imitating another program's look.

Failures (it fails even if it technically works):

1. Any text below 4.5:1 contrast on the surface it sits on, or any control, icon, focus ring or chart line below 3:1.
2. Any value (colour, size, spacing) written outside the design system.
3. Any panel, tab bar or toolbar appearing twice, or a hidden panel leaving anything behind on screen.
4. A chart or lane squashed below its minimum height instead of scrolling.
5. Text cut off without "…" and a tooltip with the whole text.

## 3. What the owner decided

1. A real design system for the whole project, grounded in a study of interface research, not copied from another program.
2. Dark only, in the Black variant (variant E of `dark-variants.html`): a true black window and viewport with near black panels.
3. The font and icons are bundled so every computer shows the same thing.
4. Active tabs are shown as a segmented control (option B of `tab-styles.html`), not with a thin coloured line.
5. The Lab screen as drawn in `lab-screen.html` (owner: "it's good now, go ahead").
6. The window keeps the operating system's own title bar; the ΜΝΗΜΟΣΥΝΗ top bar sits below it (owner, after the builder check).
7. The Pathways panel moves out of Explore; routes open from the Pathways workspace (owner, after the builder check).

## 4. The rules the design rests on

The study behind these rules, with its sources, is recorded in the conversation of 2026-10-29 and summarised here:

1. On dark surfaces depth is shown by lightness, not shadows: each raised level is a little lighter (Material dark theme guidance).
2. Text needs 4.5:1 against the lightest surface it can sit on; controls, borders that identify a control, focus indicators, icons and chart lines need 3:1 (WCAG 2.2, 1.4.3 and 1.4.11).
3. Desktop body text is about 13, captions 12, 10 the least (Apple HIG and Fluent 2 type ramps).
4. Spacing comes in steps of 4 inside components and 8 between them; nothing off the grid (Windows spacing guidance).
5. Time series that are compared are drawn as small multiples: aligned, the time axis drawn once at the bottom, each plot with its own scale and unit, as little non data ink as possible (Tufte; small multiples practice).
6. Font Inter (SIL Open Font Licence), designed for screens, with figures of equal width. Icons Lucide (ISC licence), one outline style on a 24 grid.

## 5. Foundations

### 5.1 Colours (Black variant)

Surfaces:

1. `s0` #000000: window background, the 3D view, slices.
2. `s1` #0a0a0c: every docked panel, the top bar, the status bar.
3. `s2` #131317: raised: hover, cards, chart plot backgrounds where needed.
4. `s3` #1c1c21: overlay and active: the active segment of a segmented control, menus, tooltips, pressed buttons.
5. `line` #202026: dividers and panel borders (decorative).
6. `control` #6a6a75: borders that identify a control (inputs, checkboxes); 3.7:1 on `s1`.

Text: `text` #f2f2f2 (15.2:1 on `s3`), `text2` #b4b4bc for labels, units and secondary text (8.2:1 on `s3`), `text3` #6e6e78 for disabled text and placeholders only, never for content.

Signals: `accent` #3d6fd6 for selection, primary actions and focus (white text on it 4.7:1), `accent_text` #6d98f2 for links and references on dark, `edited` #e4b04e for changes and edited values, `raised` #f0955f and `lowered` #7cb0ff for values above and below normal, `normal` #8a8a95 for the untouched normal run, `danger` #ec6f62 and `success` #5fbf8f. Every signal colour passes 3:1 on `s3` and 4.5:1 where it is used as text.

Structure colours in the 3D view and slices stay those of the atlas.

### 5.2 Type

Inter, bundled (regular 400, medium 500, semibold 600), with tabular figures on. Sizes in pixels:

1. Title 22 / 28, 600: the selected structure's name in the Info panel; dialog titles.
2. Heading 15 / 20, 600: section headings inside panels.
3. Body 13 / 20, 400: all running text and list rows.
4. Label 13 / 20, 500: field labels, the active segment, buttons.
5. Secondary 12 / 16, 400: units, hints, sources, status bar.
6. Data 11 / 14, 500: chart axes, ruler marks, group headings in lists (uppercase, 0.05 em spacing).

The ΜΝΗΜΟΣΥΝΗ wordmark keeps GFS Didot, used only for the wordmark.

### 5.3 Spacing, sizes, corners

1. Spacing steps: 4, 8, 12, 16, 24, 32.
2. Heights: controls (buttons, inputs, selects, segmented controls) 28; list and tree rows 28; panel headers and the top bar 40; the status bar 24; timeline lanes 44; chart rows 56 at the least.
3. Corners: 4 for small marks (checkboxes, key caps), 6 for controls, 8 for panels, cards and blocks.
4. Icons 16 in toolbars, lists and controls, 14 in panel header buttons, 20 in empty states; stroke 1.75.
5. Panel inner padding 12 horizontally; list indent per tree level 16.

### 5.4 Icons

Lucide icons, bundled as SVG and tinted from the colour roles. An icon is used where it says something faster than a word (actions in toolbars, kinds of change, workspaces); otherwise text. Every icon button has a tooltip with its name and shortcut ("Frame selection  F"). The set used:

1. Workspaces: brain (Explore), layers-2 (Slices), route (Pathways), flask-conical (Lab).
2. View: eye-off (Hide, H), scan (Isolate, I), eye (Show all, U), waypoints (Tracts, T), rotate-ccw (Reset view, R), maximize (Frame, F), crosshair (Centre slice, C), graduation-cap (Quiz, Q), info (About, F1).
3. Lab: play, pause, skip-back, undo-2, redo-2, git-compare-arrows (Compare), camera (Snapshot), activity (system), clock-3 (run length), and per kind of change: scissors (remove), unlink (cut), pill (drug), calendar-days (course), heart-pulse (condition), zap (stressor), test-tube (test).
4. Panels: search, more-horizontal (panel menu), chevron-right and chevron-down (tree), check (checkbox), zoom-in and zoom-out, network (Circuit).

## 6. Components

Each is one implementation used everywhere:

1. Top bar (40), below the system title bar, which stays as it is and keeps the window title (with the experiment's file name and unsaved mark): wordmark, menus, the workspace's actions as icon buttons in groups split by thin dividers, pickers (select controls), and at the right the workspace switch as a segmented control with an icon and a name per workspace. It replaces today's separate menu bar row and text toolbar.
2. Panel (dock): a 40 high header holding either the panel's name (uppercase data style) or, for tabbed panels, a segmented control of its tabs; header buttons at the right (search, panel menu); the panel can still be dragged, floated, tabbed and closed. Tabs never sit at the bottom of a panel.
3. Segmented control: used for panel tabs, Brain and Circuit, and the workspace switch; the active segment is `s3` with `text`, the rest `text2`; no coloured line.
4. Buttons: primary (accent fill), secondary (`s3`), ghost (text only), icon (28 square).
5. Inputs and spin boxes: 28 high, `s0` fill, `control` border, unit shown at the right in `text2`; focus is an accent border with a soft accent ring; edited values have an `edited` border.
6. Lists and trees: 28 rows; hover `s2`; selection an accent tint with a 2 px accent bar at the left; checkboxes 14 square with a `control` border, checked filled with accent; group headings in the data style; long text ends in "…" with a tooltip.
7. Search field: 28 high with a search icon, placeholder in `text3`.
8. Cards: `s1` at 90% over the viewport, `line` border, 8 corners; used for the Lab's parts outside the brain and for viewport labels.
9. Chips: rounded labels for small status (an effect in the Why chain, "1 value edited").
10. Status bar (24): context on the left, key hints with key caps on the right.
11. Tooltips and menus: `s3`, `line` border, 6 corners.
12. Charts: one chart style for the Lab and the Activity panel (section 8).

## 7. Layout rules

1. The 3D view (or slice view in Slices) keeps a minimum width of 480 px and never shrinks below it; side panels give way first.
2. Default panel sizes at a 1440 by 900 window: left 248, right 320, bottom a third of the height (about 290). At other window sizes they scale with the window, and below 1100 px wide the right panel tabs into the left one. These rules shape the default layouts (first start and Reset layout) at the current width only; they never rearrange a layout the user arranged (my call).
2a. In Slices the slice view gets the 480 px minimum; the 3D view keeps 240 above 1100 px wide and may collapse below that (my call).
3. A panel's content scrolls when it does not fit; it never squashes rows, lanes or charts below their minimum heights.
4. Every workspace opens with only its own panels (section 9); a panel belongs to one place in a workspace, and hidden panels leave nothing behind. Panels of other workspaces stay reachable from the Window menu, hidden by default.
5. At 850 px wide every workspace still shows its main view and its panels without overlap.

## 8. Charts

1. Lab Charts and the Activity panel use small multiples: one row per value, stacked in one column, each row 56 high at the least, a name column of 150 at the left with the value's name, unit and its value at the playhead, the plot with its own range shown as two small marks (top and bottom), and the time axis drawn once at the bottom. The normal run is grey behind the run; the playhead is one thin line through all rows. More rows than fit make the panel scroll.
2. No SI prefixes on axes; units are words ("times normal", "µg/dL").
3. No legends over data; series are named in the name column, colour matching the line.
4. Lab Timeline lanes keep their own name column (name and unit) and the ruler at the top.
5. The Activity panel's schematic curves show their note and references in the name column area or below, never over the plot.

## 9. Workspaces after the redesign

The arrangement and behaviour of decision 65 stay; what each shows is made clear:

1. Explore: Structures (left), the 3D view (centre), Info and Slices tabbed as a segmented pair (right). The Pathways panel is no longer here.
2. Slices: Structures (left), the slice view large (centre right), Info (right, narrow) and the 3D view kept visible in the centre at its minimum.
3. Pathways: the Pathways panel (left), the 3D view (centre), Info and Slices as a segmented pair (right), so a route step still centres the slice, and the Activity panel (bottom) as decision 47 says.
4. Lab: as `lab-screen.html`.

Removing the Pathways panel from Explore is a change decided by the owner: routes open from the Pathways workspace, reached with Ctrl+3 or the workspace switch. A quiz still opens its panel in whichever workspace it starts, as today.

## 10. Each part of the app

Every view moves to the design system; for each, the visible result:

1. Structures tree (`views/structure_tree.py`): search field, 28 rows, real checkboxes, full names until the panel edge then "…" with a tooltip.
2. Info panel (`views/info_panel.py`): title in the title style without awkward wrapping, side and kind as a secondary line, sections as headings, references as secondary text, the draft note as a chip, the disclaimer as a quiet card at the end in `text2`, not red.
3. Slices (`views/slice_panel.py`): Brain and Spinal cord, and Axial, Coronal and Sagittal, as segmented controls; the slider and the labels opacity slider restyled; orientation letters in the data style.
4. Pathways panel (`views/pathway_panel.py`): route list with group headings, the route's title and start, the side switch as a segmented control, play controls as icon buttons, steps as a numbered list, details in body text, "Open in the Lab" and "Leave pathway" as secondary buttons.
5. Activity panel (`views/activity_chart.py`): small multiples per section 8.
6. Quiz panel and quiz setup (`views/quiz_panel.py`, `views/quiz_setup.py`), progress dialog, About dialog: the same components, titles and buttons.
7. 3D view (`views/brain_view.py`, `lab/brain_overlay.py`): background `s0`, the selection outline and labels in the design colours and Inter; viewport tools as a small icon group at the top right; the Lab's labels and parts outside the brain as cards.
8. Lab panels (`lab/`): as `lab-screen.html`, including the circuit view with 13 body text in boxes sized to their content and arrows in the signal colours.
9. Main window (`main_window.py`, `workspaces.py`, `app.py`): the top bar, the status bar, the Window menu, panel headers, and the stray and duplicate tab bars removed.

## 10a. Menus and actions (my call)

1. Menus: File, Edit (undo and redo, in the Lab), View (Hide, Isolate, Show all, Tracts, Reset view, Frame selection, Centre slice), Study (quiz and progress), Experiment (in the Lab only), Window, Help (About, the guide on the website).
2. Top bar actions per workspace: Explore and Slices: Hide, Isolate and Show all, then Tracts, then Quiz; Pathways: Tracts and Quiz; Lab: as `lab-screen.html`.
3. Viewport group at the top right of the 3D view in every workspace: Frame selection, Reset view, Tracts. Centre slice sits in the slice panel's header.
4. Every shortcut works where it works today, in every workspace; nothing is turned off because its button moved.

## 10b. Where the approved mockup and the rules differ (my call)

1. The rules win: group headings, units under lane names, chart ticks and hints use `text2`, not `text3`, so they reach 4.5:1; inputs, selects and segmented controls get the `control` border at 3:1; sizes use the type ramp (13, 12, 11), not the mockup's 12.5, 11.5 and 10.5. The built screens are therefore a little brighter in those places than `lab-screen.html`.
2. Run lines in the Lab keep one colour per value (a fixed data palette passing 3:1 on `s1`), the snapshot line is the same colour dashed, and only the value at the playhead is coloured `raised` or `lowered` by direction, so playback costs nothing extra.
3. Each kind of change gets its icon from an optional `icon` field in the model file's experiments and tests (falling back to one icon per group), so a new system chooses its own icons. This adds one optional field to the model format and the stress model file; nothing else in the model changes.

## 11. Constraints

1. PySide6 6.12 with Qt widgets, VTK and pyqtgraph as today; no web views.
2. The design system lives in one package (for example `cns_desktop/design/`): colour roles, type, spacing, sizes, icons, and the one application stylesheet built from them. Views read from it; tests can check that no view writes its own colours or sizes.
3. Inter and Lucide ship in the repository and in the packages with their licence texts, and are listed in the About box and README with their licences.
4. Speed limits stay as they are (decisions 31, 36, 43, 44 and the Lab budgets); the redesign must not make any timing test slower beyond its allowance.
5. Texts keep the project rules: no dashes as punctuation in UI text, plain English.
6. The existing behaviour tests stay green; tests that read text or layout are updated only where this document changes what is shown.

## 12. Left to the builder

1. How the panel header holds the segmented tabs (for example custom dock title widgets that keep dragging and floating).
2. Which icons the Lucide set provides under each name above, if a name differs.
3. Exact stylesheet structure and how icons are tinted.
4. The exact sizes at other window widths, within section 7.
5. How the tests check contrast, minimum sizes and that no panel appears twice.

## 13. Out of scope

1. A light theme.
2. New features, new workspaces, new Lab systems.
3. Translating texts.
4. Changes to the atlas data or the Lab model, other than the optional `icon` field of section 10b.

## 14. Decisions to log

1. Mnemosyn has one design system (colours, type, spacing, sizes, icons) defined in one place; the Black dark theme only for now.
2. Inter and Lucide are bundled so every computer looks the same.
3. Tabs and switches are segmented controls; tabs sit at the top of panels.
4. Charts are small multiples with one time axis and no legends over data.
5. Each workspace shows only its own panels; the Pathways panel lives in the Pathways workspace.
