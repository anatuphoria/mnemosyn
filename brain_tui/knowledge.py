from __future__ import annotations

import json
import os

BUILTIN: dict[str, dict] = {
    "Frontal_Sup_L": {"function": "Executive planning, working memory, voluntary eye movements.", "connections": "Parietal cortex, striatum, contralateral frontal.", "disorders": "Dysexecutive syndrome, abulia when damaged."},
    "Frontal_Sup_R": {"function": "Executive planning, working memory, voluntary eye movements.", "connections": "Parietal cortex, striatum, contralateral frontal.", "disorders": "Dysexecutive syndrome, neglect-like inattention."},
    "Frontal_Mid_L": {"function": "DLPFC: reasoning, language production support (Broca nearby).", "connections": "Broca area, parietal, basal ganglia loops.", "disorders": "Depression, executive dysfunction."},
    "Frontal_Mid_R": {"function": "DLPFC: monitoring, inhibition, spatial working memory.", "connections": "Parietal, cingulate, basal ganglia.", "disorders": "Impulsivity, executive dysfunction."},
    "Precentral_L": {"function": "Primary motor cortex (M1): right-body voluntary movement.", "connections": "Premotor, SMA, corticospinal tract.", "disorders": "Contralateral weakness, Jacksonian march."},
    "Precentral_R": {"function": "Primary motor cortex (M1): left-body voluntary movement.", "connections": "Premotor, SMA, corticospinal tract.", "disorders": "Contralateral weakness."},
    "Postcentral_L": {"function": "Primary somatosensory cortex (S1): right-body touch/proprioception.", "connections": "Thalamus (VPL), motor cortex.", "disorders": "Cortical sensory loss, astereognosis."},
    "Postcentral_R": {"function": "Primary somatosensory cortex (S1): left-body touch/proprioception.", "connections": "Thalamus (VPL), motor cortex.", "disorders": "Neglect, sensory loss."},
    "Parietal_Sup_L": {"function": "Visuospatial integration, reaching, calculation.", "connections": "Occipital, frontal eye fields.", "disorders": "Gerstmann syndrome, apraxia."},
    "Parietal_Sup_R": {"function": "Spatial attention, body schema.", "connections": "Occipital, frontal.", "disorders": "Hemispatial neglect."},
    "Temporal_Sup_L": {"function": "Auditory cortex + Wernicke: speech comprehension.", "connections": "Heschl gyrus, arcuate fasciculus.", "disorders": "Receptive aphasia."},
    "Temporal_Sup_R": {"function": "Auditory processing, prosody, music.", "connections": "Contralateral temporal, limbic.", "disorders": "Aprosodia, auditory agnosia."},
    "Occipital_Mid_L": {"function": "Visual association cortex.", "connections": "V1 calcarine, parietal/temporal streams.", "disorders": "Visual agnosia, field cuts."},
    "Occipital_Mid_R": {"function": "Visual association cortex.", "connections": "V1 calcarine, parietal/temporal streams.", "disorders": "Prosopagnosia (right dominant)."},
    "Hippocampus_L": {"function": "Verbal episodic memory encoding.", "connections": "Entorhinal, fornix, Papez circuit.", "disorders": "Alzheimer amnesia, TLE."},
    "Hippocampus_R": {"function": "Spatial/episodic memory encoding.", "connections": "Entorhinal, fornix.", "disorders": "Topographic amnesia, TLE."},
    "Amygdala_L": {"function": "Fear conditioning, emotional salience.", "connections": "Hypothalamus, OFC, brainstem.", "disorders": "Anxiety, Kluver-Bucy (bilateral)."},
    "Amygdala_R": {"function": "Fear conditioning, emotional salience.", "connections": "Hypothalamus, OFC.", "disorders": "Anxiety, emotional blunting."},
    "Thalamus_L": {"function": "Sensory/motor relay + consciousness gate.", "connections": "All cortex, basal ganglia.", "disorders": "Thalamic pain, coma (bilateral)."},
    "Thalamus_R": {"function": "Sensory/motor relay + consciousness gate.", "connections": "All cortex.", "disorders": "Thalamic pain syndrome."},
    "Insula_L": {"function": "Interoception, taste, empathy.", "connections": "Operculum, limbic, brainstem.", "disorders": "Anosognosia, addiction relapse."},
    "Insula_R": {"function": "Interoception, bodily self-awareness.", "connections": "ACC, amygdala.", "disorders": "Neglect, autonomic dysregulation."},
    "Caudate_L": {"function": "Goal-directed action, procedural learning.", "connections": "DLPFC-OFC loops.", "disorders": "Huntington, OCD."},
    "Caudate_R": {"function": "Goal-directed action, procedural learning.", "connections": "Frontal-striatal loops.", "disorders": "Huntington, impulsivity."},
    "Cerebellum_6_L": {"function": "Coordination, timing, cognitive modulation.", "connections": "Pons, thalamus, cortex.", "disorders": "Ataxia, dysmetria."},
    "Cerebellum_6_R": {"function": "Coordination, timing.", "connections": "Pons, thalamus.", "disorders": "Ataxia."},
    "Brainstem_Pons": {"function": "Relay cortex<->cerebellum; sleep/arousal nuclei.", "connections": "Cerebellar peduncles, CN V-VIII.", "disorders": "Locked-in (ventral), ataxia."},
    "Brainstem_Medulla": {"function": "Cardiorespiratory centers, CN IX-XII.", "connections": "Spinal cord, cerebellum.", "disorders": "Wallenberg, fatal if bilateral."},
    "Brainstem_Midbrain": {"function": "Eye movements (CN III/IV), dopamine (SN/VTA).", "connections": "Thalamus, basal ganglia.", "disorders": "Weber, Parkinsonism."},
}

DEFAULT_ENTRY = {"function": "Association cortex - integrates distributed inputs for its network.",
                 "connections": "Ipsilateral + contralateral homologue via corpus callosum.",
                 "disorders": "Focal lesion causes network-specific deficit."}


class KnowledgeBase:
    def __init__(self, json_path: str | None = None):
        self.data: dict[str, dict] = dict(BUILTIN)
        if json_path and os.path.exists(json_path):
            try:
                with open(json_path) as f:
                    extra = json.load(f)
                if isinstance(extra, dict):
                    self.data.update(extra)
            except Exception:
                pass

    def get(self, name: str) -> dict:
        return self.data.get(name, DEFAULT_ENTRY)

    def search(self, query: str, names: list[str], limit: int = 12) -> list[str]:
        q = query.strip().lower()
        if not q:
            return names[:limit]
        scored: list[tuple[int, str]] = []
        for n in names:
            nl = n.lower()
            if nl == q:
                scored.append((0, n))
            elif nl.startswith(q):
                scored.append((1, n))
            elif q in nl:
                scored.append((2, n))
        scored.sort(key=lambda t: (t[0], t[1]))
        return [n for _, n in scored[:limit]]
