# Water balance, the second Lab system

Date: 2026-11-01
Status: approved by the owner in conversation on 2026-11-01
Builds on: the Simulation Lab (decisions 63 to 66), its stress axis model (`atlas_src/models/stress.toml`),
the one Lab timeline (decision 75), lesion mode (decision 76)

## 1. Why

Lesion mode and a second Lab system are the last main features before the work turns to
enhancements, fixes and the handbook (roadmap). The owner chose water balance over sleep and
blood pressure: it follows the hormone axis pattern that already works for the stress axis, its
anatomy (the supraoptic and paraventricular nuclei) is in the public atlas, and its signature test,
the water deprivation test with desmopressin, is what exams ask about.

## 2. Goals, non goals, what would make it fail

Goals:

1. A computed model of plasma osmolality and sodium, vasopressin, urine concentration and flow,
   body water, thirst and drinking, in real units, every number cited.
2. The experiments and tests listed in section 4, each explained by the Why chain from declared
   links, like the stress axis.
3. A behaviour circuit "Thirst and water balance" in the Pathways panel whose "Open in the Lab"
   opens this system.
4. In the app it is a second choice in the Lab's system picker; nothing else about the Lab changes.

Non goals: linking it to the stress axis or any other system (each system runs alone; a later
design may connect them); blood pressure and volume reflexes beyond what the experiments need;
fitting to one person; new Lab screens.

It fails if a value leaves its published range on a normal day, if any number or sentence lacks a
source, if the water deprivation test gives the wrong answer for any of normal, central diabetes
insipidus, nephrogenic diabetes insipidus or primary polydipsia, or if the stress axis changes.

## 3. The model (`atlas_src/models/water.toml`)

Values (lanes in order): plasma sodium (mmol/L), vasopressin (pg/mL), urine osmolality (mOsm/kg),
thirst (times normal). Without lanes: body water (L), body osmoles, plasma osmolality (mOsm/kg),
urine flow (mL/min), drinking (mL/min), desmopressin, gut water.

Relations, each with its source, numbers settled by the builder within the cited ranges:

1. Plasma osmolality is body osmoles over body water; plasma sodium follows it (about half of it).
2. Vasopressin secretion rises linearly with plasma osmolality above a threshold of about 281 to
   284 mOsm/kg, slope about 0.35 to 0.63 pg/mL per mOsm/kg (Robertson and Athar 1976; Baylis and
   Robertson 1980). Its plasma half life is about 24 minutes (Baumann and Dingman 1976).
3. Urine osmolality rises with vasopressin from about 50 to about 1200 mOsm/kg, saturating
   (Robertson and colleagues 1973 and 1976). Urine flow is the solute excreted over the urine
   osmolality.
4. Thirst rises above an osmotic threshold a little higher than vasopressin's and drives drinking;
   a normal day adds habitual drinking at meals; insensible losses run all the time.
5. Desmopressin acts like vasopressin on the kidney and lasts hours, not minutes.

Parts: osmoreceptors (no atlas shape; a text step and a card), supraoptic and paraventricular
nuclei (atlas structures), posterior pituitary (atlas structure where the build has it), kidney and
blood (cards outside the brain).

## 4. Experiments and tests

Experiments: drink a litre of water; stop drinking; salty (hypertonic) infusion; desmopressin;
central diabetes insipidus; nephrogenic diabetes insipidus; SIADH; primary polydipsia.

Tests:

1. **Water deprivation test.** No drinking for 8 hours, then read urine osmolality. Normal: it
   concentrates well; diabetes insipidus: it stays dilute.
2. **Desmopressin test.** Desmopressin given at the end of deprivation, urine osmolality read two
   hours later and compared with the same run without it. A rise of more than half points to a
   central cause; almost none to the kidney (or to normal kidneys already at their maximum).

The engine gains what these need: a test may withhold or change a value for a stretch of time (as
experiments already do), and a new rule "rises by", the mirror of "suppressed by". The builder
decides the exact file fields.

## 5. Checks

Automatic checks hold the model to published facts, at least: plasma sodium stays within 135 to
145 mmol/L and urine osmolality within its normal range on a normal day; a drunk litre of water is
mostly excreted within about 3 to 4 hours; 8 hours without water concentrates normal urine well
above 600 mOsm/kg; in central diabetes insipidus urine stays dilute after deprivation and rises by
more than half after desmopressin; in nephrogenic diabetes insipidus it barely rises; in SIADH with
normal drinking plasma sodium falls below 135 mmol/L.

## 6. Texts and the route

`atlas_src/knowledge/en/lab-water.toml` describes every value, parameter, link, experiment, test
and normal day note, cited, drafts like the stress axis texts. The behaviour circuit "Thirst and
water balance" (both sides) runs from the osmoreceptors through the supraoptic and paraventricular
nuclei to the posterior pituitary, with Role, Disorders and Drugs lines per step, cited.

## 7. Left to the builder

Exact equations and parameter values within the cited ranges, the normal day schedule, file field
names for the new test features, the card layout, and the speed budgets (no slower than the
stress axis).

## 8. Decisions to log

1. Water balance is the second Lab system, independent of the stress axis.
2. Lab tests may change a value for a stretch of time and may use the rule "rises by".
