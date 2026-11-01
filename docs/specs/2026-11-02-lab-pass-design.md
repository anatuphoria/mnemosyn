# Lab pass: a bigger brain view and settings you can see

Date: 2026-11-02
Status: approved by the owner in conversation on 2026-11-02
Builds on: the Simulation Lab (decisions 63 to 66), the one Lab timeline (decision 75), water balance
(decision 78), the design system (`cns_desktop/design/`)

## 1. Why

After 0.4.0 the owner used the Lab and found two things that make it feel unfinished:

1. The 3D brain looks small. The "Outside the brain" column (`Strip` in
   `cns_desktop/lab/viewport.py`, a fixed 200 px beside the view) is mostly empty black space, and
   the camera frames the whole scene, including the spinal cord and the wide slice plane, so the
   brain fills only about a third of the view height.
2. The Model tab is a long flat list of number boxes. Changing a setting tells you nothing about
   what it means or how far from normal you are.

The owner wants both fixed in one pass, before the handbook takes its screenshots.

## 2. Goals, non goals, what would make it fail

Goals:

1. The 3D view gets its full width: the parts outside the brain float as cards over the view.
2. The brain fills the view when the Lab opens and when the view is reset.
3. The Model tab groups its settings by what they do and gives each setting a control that fits
   its kind (section 4), so a student sees how far from normal a value is and what it shapes.

Non goals: a body figure (tried in a mockup on 2026-11-02 and dropped by the owner); changing
any model number, equation, experiment or test outcome; changes to the timeline, the circuit view,
the Why panel or the Inspector; a Settings window.

It fails if any model result changes, if a value can no longer be typed exactly, if a card hides
the brain or a label at the default window size, if the panel becomes slower to open than today in
a way a person notices, or if the Model tab clips or overflows at the narrowest panel width (200 px,
`SIZE["panel_min"]`). The Model tab may not raise that minimum.

## 3. Layout

1. Remove the side column. The cards (`StripCard`) float over the top right corner of the 3D view,
   stacked, on a slightly see through card background (design system surface with alpha), with the
   same small heading "OUTSIDE THE BRAIN". They keep today's behaviour: click selects the part,
   right click opens the same menu, the tone shows raised or lowered.
2. The cards are hidden in the Circuit view, as the column is today, and outside the Lab.
3. When the view is narrow (under `SIZE["narrow"]`, or when the cards would cover more than a
   quarter of the view height), each card shows one line: the part name and its value, for example
   "Blood · 14.2 µg/dL". The full two line card comes back on hover. (Builder check, settled in
   design.)
4. Framing: when the Lab is entered, when the system changes, and on the view's reset button while
   in the Lab, the camera frames the brain (cerebrum, brainstem and cerebellum) rather than the scene
   bounds that include the cord and the slice plane, leaving room for the floating cards on the
   right. Outside the Lab, framing stays as it is.

## 4. The Model tab

### 4.1 Groups

Settings appear under small group headings (the design system's `data` role, like "OUTSIDE THE
BRAIN"). Each model file names the group of each setting. Proposed groups:

1. Stress axis: Removal and turnover; Feedback; Daily rhythm; Stress; Surgery and disease; Drugs.
2. Water balance: Vasopressin; Kidney; Thirst and drinking; Water and salt; Drugs; Disease.

### 4.2 Kinds of control

Each setting declares a kind in its model file. Every kind keeps a typeable number field showing the
real value and unit, the per row reset button, the amber "edited" tone, and the tooltip with meaning
and sources that rows have today. Reset all stays.

1. `rate`: a slider on a logarithmic scale between `low` and `high`, with marks at ⅓×, ½×, normal,
   2× and 3× where they fall inside the range. The field always holds and accepts the real value
   and unit, never a multiple. When edited, a small badge beside it reads the multiple (for example
   "2× normal") and a one line plain note from the model texts appears under the slider (for example
   "ACTH clears twice as fast"). Used for removal, turnover, absorption and response rates.
2. `curve`: two or one settings shown together as a small graph of the relation they shape, with
   the normal curve dashed behind the current one. The main handle is dragged along the x axis
   (the halfway point or threshold); the second setting (steepness or sensitivity) changes by
   scroll on the graph and by its own typeable field under the graph. Curves are declared in the model
   file with their settings, the x quantity and range, axis words, and the expression to draw,
   evaluated with the model's expression rules. Proposed curves:
   1. Stress: GR feedback (`K_GR`, `n`; `hill(x, K_GR, n)`), MR feedback (`K_MR`), adrenal
      saturation (`K_sat`), tumour GR feedback (`K_tumour`, with `n` shown read only).
   2. Water: kidney response to vasopressin (`K_u`, `n_u`), vasopressin release (`avp_threshold`,
      `avp_slope`), thirst (`thirst_threshold`, `thirst_slope`), thirst drinking (`drink_threshold`,
      `drink_gain`, capped by `drink_max` drawn as a ceiling).
3. `clock`: a slider labelled in clock time (0:00, 6:00, 12:00, 18:00, 24:00), the field showing
   hours and minutes. The 12 hour setting (`phase2`) uses a 12 hour scale.
4. `switch`: a segmented control with named stops declared in the model file, for settings that
   stand for a state more than an amount: `stalk` (Intact 1, Half 0.5, Cut 0), `avp_scale` (Normal
   1, Partial 0.5, None 0.05), `kidney` (Normal 1, Partial 0.5, None 0.05). When the value is not on a
   stop, no stop is selected and the field shows the value. The exact value is set through the field,
   which is shown on right click or by a small "exact" toggle.
5. `slider`: a linear slider between `low` and `high` with a tick at normal. Everything not listed
   above, for example `stress`, `acth_tumour`, `depth`, the water thresholds that are not in a curve.

### 4.3 When results update

Decided by the owner on 2026-11-02: on release. While a slider, a curve handle or a scroll on a
curve moves, only the control itself moves live (handle, badge, note, the drawn curve). The run,
and with it the timeline, the brain colours and the cards, is recomputed once when the mouse is
released, or once per scroll step settled after a short pause. One drag is one undo step. This
matches how a change is dragged on the timeline today. (A rerun takes about 20 ms for water balance
and about 270 ms for the stress axis over one day, so live reruns would stutter.)

## 5. Model files

The kind, group, curve and switch stops live in `atlas_src/models/*.toml` and pass through the atlas
build like the other model fields (`cns_atlas/models.py`, `tools/build_atlas/`). A setting without a
kind falls back to `slider`, and a setting without a group goes under "Other", so a new system works
before it is tuned. The atlas tests check that every curve names real settings, that switch stops lie
within `low` and `high`, and that `rate` settings have `low > 0`.

## 6. Checks

1. All existing model, experiment and Lab tests pass unchanged in their results.
2. Widget tests for each kind: dragging or typing sets the document value; reset returns to normal;
   edited tone; a curve's handle moves the halfway point; a switch stop sets its value.
3. A layout test at the default window size: no card overlaps the brain's projected bounds, and the
   brain's projected height is at least half the view height after entering the Lab.
4. Screenshots of both systems at 1440 by 900 and at the narrow width, reviewed before merge.
5. The Model tab at 200 px shows every control without clipping, and the panel minimum stays
   `SIZE["panel_min"]`. When the width is tight, curves and switches stack under the setting name.

## 7. Left to the builder

1. Exact sizes, spacing and how the graphs are painted (custom painted widgets on the design
   tokens are expected; no new dependency).
2. The final wording of group names and the one line notes, from the model texts.
3. How the floating cards are placed over the VTK view (a child widget over the render widget, or
   drawn in the label layer) as long as they stay clickable and readable.
4. Whether the existing `QDoubleSpinBox` stays as the typeable field.

## 8. Decisions to log

1. In the Lab, the parts outside the brain float as cards over the 3D view, and the brain is
   framed to fill the view.
2. Each Lab setting declares a kind (rate, curve, clock, switch, slider) and a group in its model
   file, and the Model tab draws a control for that kind.
