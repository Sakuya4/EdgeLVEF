# Architecture figure specification

The figure uses an AI-assisted layout reference, followed by an editable SVG reconstruction checked against the implemented model and loss. The published PNG is rendered from that SVG at 300 dpi; the PDF preserves vector geometry and text. Its content specification follows.

To regenerate the publication files, install `requirements-figures.txt`, then run `python docs/assets/render_architecture.py` and `python docs/assets/generate_benchmark_figures.py` from the repository root.

## Original specification

Create a technically exact black-and-white two-panel scientific neural-network architecture figure for an IEEE biomedical imaging journal article, titled "EdgeLVEF: PLAX video knowledge distillation". Use a wide landscape white canvas, restrained thin black rules and arrows, no colors, no gradients, no 3D decorations, no invented ultrasound or clinical images. Clean typography, consistent font size, generous margins. It must be readable at two-column journal width. This is a rigorous architecture schematic, not a generic infographic. Exact spelling of every label and faithful arrow meanings are essential.

Panel (a), top: "Offline Teacher-Student learning".
Three aligned horizontal lanes:
Top lane: "PLAX cine" then "64 frames, 112 x 112" then "R(2+1)D-18 x 2" then "Mean ensemble"; two outputs from ensemble, labelled "Teacher EF" and "Teacher feature (512-D)".
Middle lane: same PLAX cine, "32 frames, 112 x 112" then "Edge Student" then two outputs "Student EF" and "Student feature (256-D)". The Student also has a "Low-EF logit" output.
Bottom area: four separately numbered loss terms, exact text:
"Report supervision: Huber"
"EF distillation: 0.50 Huber"
"Low-EF transfer: 0.20 BCE"
"Feature alignment: 0.10 cosine loss"
Show dashed supervision arrows to appropriate losses, not false inference dependencies: report EF and Student EF to first loss; Teacher EF and Student EF to second; Teacher EF-derived soft target and Low-EF logit to third; Teacher feature and Student feature via "Projector 256 -> 512" to fourth. If arrow routing would be cluttered, use four aligned simple mathematical label pairings instead of crossed arrows. The fourth term is cosine distance. The low-EF soft target equals sigmoid((40 - Teacher EF)/5). Put this formula as a small single-line note in panel a if readable. A small note "Teacher and projector are training-only" must be legible. No implication that Teacher supplies image inputs or that source PLAX is an A4C view.

Panel (b), bottom: "Compact Student inference".
A left-to-right chain of clear rectangular modules:
"32-frame grayscale PLAX cine" ->
"MobileNetV3-Large + TSM" ->
"Frame projection 960 -> 128" ->
"Residual depthwise TCN: d = 1, 2, 4" ->
"Temporal mean + max pooling: 256-D" ->
two outputs, "LVEF estimate" and "Low-EF score".
Put below this path "3,212,755 parameters". Put a small independent box BELOW the path labelled "PLAX Readiness Gate" with subline "MobileNetV3-Small; view / readiness / quality". Connect only from input cine to this independent box, do not connect it into Teacher or Student features; it is a system-side assessment module, not part of the LVEF network. Do not invent segmentation, LV landmarks, ED/ES volume, physics equations, calibrated uncertainty, clinical validation, NPU latency, or performance charts.
Solid arrows are inference computations, dashed arrows training supervision. Provide a minimal two-symbol legend. Use exact factual module labels, no M-series or H-series experiment IDs, and no numerical EF example output. Prioritize accuracy and legibility over visual ornament.

## Computational dependency correction

Edit this scientific architecture diagram with one precise correction only. In panel (a), REMOVE the vertical dashed arrow pointing down from 'Teacher feature (512-D)' into 'Projector 256 -> 512'. Teacher features must NOT enter the Student projector. Preserve the existing solid arrow from 'Student feature (256-D)' into that projector. Keep the separate loss pairing 'Teacher feature (512-D)' and 'Projected student feature (512-D)' leading to the Feature alignment loss. Keep every other box, arrow, word, number, spacing, black-and-white journal style and both panels exactly unchanged. This arrow removal corrects the implemented computational dependency. No added features or decorations.
