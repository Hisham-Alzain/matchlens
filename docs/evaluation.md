# Evaluation

Every pipeline stage is measured against external ground truth. Perception is scored on a
public tracking benchmark; the event rules are scored on full matches from two independent
data providers. The numbers below are the ones the system actually produced, including the
weak ones. Audit date: August 2026.

| | |
|---|---|
| Perception frames scored | 36,750 |
| Annotated objects | 529,105 |
| Tracking-replay frames (event layer) | 431,924 |
| Annotated events | 3,791 |
| Automated tests passing | 614 |

## 1. Datasets and what each one measures

| Dataset | Provides | Measures | Does not provide |
|---|---|---|---|
| SoccerNet-GSR, 49 clips × 750 frames @ 25 fps (test split) | boxes, track ids, role, team, jersey, pitch positions | detection, tracking, team, role, projection | events, possession |
| Metrica Sports, 2 full matches (open data) | events with player and team ids, tracking | events, possession, statistics, calibration | real pixels (tracking is injected) |
| Sportec / DFL, 1 full match | events with player and team ids | independent replication of the event rules | crosses, interceptions (not annotated) |

GSR annotates game state, not actions, so it has no event labels. Metrica and Sportec
inject perfect tracking, so they isolate *rule* error from *perception* error. The two layers
therefore do not compose, and true end-to-end accuracy is not estimated by this audit.

## 2. Metric definitions and scoring rules

- **Precision / recall / F1** per event type, with a temporal tolerance window around the
  annotated moment.
- **Attribution ladder.** Each event is scored three times with tightening requirements:
  right *type and moment*; additionally right *team*; additionally right *player*. The step
  where recall collapses localises the defect.
- **Micro-averaging.** Counts are summed across clips and the ratio computed once. Averaging
  per-clip ratios would let a clip with eight visible players count as much as one with
  thirty, and it flatters.
- **Median with interquartile range** for metrics with no underlying counts (mAP, HOTA,
  calibration), because a mean cannot distinguish "uniformly mediocre" from "excellent except
  when it collapses".
- **Team labels are aligned before scoring.** Team assignment is a partition, not a
  classification; the evaluator resolves the best 1:1 mapping first.
- **Unknown is not false.** Abstaining components are scored on accuracy-when-known,
  coverage and unknown rate, never collapsed into one number.
- **Regression gate.** Every run is compared against a recorded baseline; a drop on any
  tracked metric fails the check.

## 3. Perception results (SoccerNet-GSR, 49 clips)

### Detection

| Class | Ground truth | Precision | Recall | mAP50 median [IQR] |
|---|--:|--:|--:|--:|
| player | 464,689 | 89.8 % | 78.2 % | 77.9 [65.0–84.3] |
| referee | 44,957 | 71.4 % | 43.9 % | 38.7 [18.3–50.7] |
| goalkeeper | 19,459 | 90.3 % | **17.5 %** | 3.0 [0.0–14.3] |
| ball | 34,129 | 51.6 % (median) | **25.1 %** | — |

Goalkeepers are precise but mostly skipped. Ball recall is the single largest constraint on
everything downstream: the longest unbroken miss has a median of 174 frames (7.0 s), which no
tracker bridges.

### Tracking

| Metric | Value |
|---|--:|
| detection precision (in tracker) | 93.3 % |
| detection recall | 73.4 % |
| IDF1 | **51.4 %** (IDP 58.4 / IDR 45.9) |
| HOTA | 44.0 % median [38.0–54.2] |
| ID switches per track | 5.79 |
| fragmentations per track | 12.62 |

Boxes are right; continuity is what fails. IDP well above IDR is the signature of a cautious
tracker that drops the thread rather than associating wrongly. The HOTA implementation uses
per-frame IoU-optimal assignment and should not be quoted directly against published HOTA
numbers without stating that.

### Projection (15 of 49 clips where a homography solved)

| | Median error | p95 | Within 1.5 m |
|---|--:|--:|--:|
| best clip | 0.59 m | 1.46 m | 96.1 % |
| pooled | 2.28 m | 6.86 m | 30.7 % |
| worst clip | 13.05 m | 20.10 m | 5.3 % |

The failure is bimodal: two clips are production-grade and one is off by a fifth of the pitch
width. The pooled median describes no actual clip, which is why the fix pursued is a validity
gate rather than a general accuracy improvement. Only 18.6 % of GSR frames obtained a
homography at all, and GSR is broadcast footage while the keypoint model is trained for
tactical cameras.

### Team and role

| Metric | Value |
|---|--:|
| team accuracy (when known) | **87.3 %** at 93.3 % coverage |
| incorrect team locks | 9.5 % of tracks |
| role accuracy (when known) | **95.0 %** at 100 % coverage |
| role flips | 0 across 1,323 tracks |
| lock latency | 0 frames (median) |

## 4. Event results (Metrica × 2, Sportec × 1)

### Per event type, two full Metrica matches (precision / recall / F1)

| Event | Match 1 | Match 2 |
|---|---|---|
| pass | 0.822 / 0.767 / **0.793** | 0.821 / 0.775 / **0.797** |
| throw-in | 0.964 / 0.964 / **0.964** | 0.886 / 0.969 / **0.925** |
| kick-off | 1.000 / 0.833 / **0.909** | 0.875 / 1.000 / **0.933** |
| corner | 1.000 / 0.727 / **0.842** | 1.000 / 0.714 / **0.833** |
| free kick | 0.769 / 0.938 / **0.845** | 0.625 / 0.833 / 0.714 |
| goal kick | 0.323 / 0.769 / 0.455 | 0.611 / 0.917 / 0.733 |
| penalty | — (none) | 1.000 / 1.000 / 1.000 |
| save | 0.667 / 0.286 / 0.400 | 0.750 / 0.500 / 0.600 |
| goal | 0.400 / 0.500 / 0.444 | 0.500 / 0.200 / 0.286 |
| shot | 0.351 / 0.542 / 0.426 | 0.321 / 0.375 / 0.346 |
| interception | 0.326 / 0.272 / 0.296 | 0.217 / 0.179 / 0.196 |
| cross | 0.273 / 0.176 / 0.214 | 0.333 / 0.333 / 0.333 |

Passes (1,026 and 1,170 annotated) and set pieces are at an acceptable level; set pieces are
defined by a static spatial pattern that can be checked unambiguously. Events defined by a
fast state transition (shots, interceptions, crosses) are not yet acceptable.

### Attribution ladder (Metrica, mean of both matches)

| Event | type | + team | + player | Defect localised at |
|---|--:|--:|--:|---|
| pass | 79.4 % | 76.0 % | 74.6 % | no collapse |
| interception | 66.5 % | 63.2 % | 36.6 % | player attribution |
| shot | 66.7 % | 0.0 % | 0.0 % | team attribution (Metrica only, see below) |

### Replication on an independent provider (Sportec)

| Event | Metrica F1 / R | Sportec F1 / R | Reads as |
|---|---|---|---|
| pass | 77.5 / 74.6 | 65.2 / 73.7 | recall replicates almost exactly; precision does not, because Sportec annotates fewer events |
| throw-in | 95.9 / 96.7 | 42.7 / 42.3 | set-piece rules tuned to Metrica's conventions |
| shot | — / 0.0 | 16.9 / 30.0 | the shot team inversion is Metrica-specific: on Sportec every detected shot had the right team |

### Possession and totals

Possession is the rule layer's strongest result: frame accuracy 75.5 to 78.3 %, dead-ball
F1 92.9 to 96.6, and the possession split within 0.36 percentage points on Sportec and 0.65
on Metrica match 2. Event confidence is poorly calibrated (ECE around 0.31), so the
confidence stamped on an event currently carries little information.

## 5. Test conditions

- Reference hardware: laptop, NVIDIA RTX 3060 6 GB, 16 logical CPUs.
- Perception runs use the fast detection tier with TensorRT FP16 at 1080p; the engine
  sustains 25 to 35 fps, i.e. real time for a 25 fps source.
- Evaluation runs are reproducible from the private repository with a single command per
  layer plus a regression gate against the recorded baselines.

## 6. What growing the benchmark changed

Three clips produced two confident conclusions that were wrong; 49 clips corrected them.

| Metric | 3 clips | 49 clips |
|---|--:|--:|
| frames with a homography | 0.0 % | 18.6 % |
| goalkeeper recall | 4.9 % | 17.5 % |
| team accuracy | 94.6 % | 87.3 % |
| ball recall | 35.7 % | 25.1 % |
| IDF1 | 50.0 % | 51.4 % |

## 7. Limitations

1. **The two layers do not compose.** Rule-layer numbers assume perfect tracking; perception
   numbers come from clips without event labels. True end-to-end accuracy is lower than either
   and is not yet measured.
2. **Domain shift.** GSR is broadcast footage; the models are tactical-camera models. Part of
   the perception gap, probably most of the projection failure, is domain shift. Our own
   tactical footage is not annotated, so accuracy on the footage the product is meant for
   remains unmeasured.
3. **Ball recall (25 %)** and **goalkeeper recall (17.5 %)** are the binding perception defects;
   every keeper-dependent feature (saves, keeper distance in xG, attacking direction) inherits
   the second.
4. **Shot and interception precision** are the binding event defects. Interceptions over-fire
   about 2.5×; the shot team inversion appears only on Metrica and is still being diagnosed.
5. **Shot outcome is unmeasured, not wrong.** The pipeline emits success/fail, never
   goal/saved/blocked, so outcome accuracy is undefined rather than zero.
6. **Possession truth is derived** from the event feed ("team of the most recent event"), not
   given, so the contested state cannot be scored.
7. **Goals.** Goal detection depends on the restart witness and on a shot being emitted first;
   on tactical footage without a line-up the scoreline is frequently under-counted.
