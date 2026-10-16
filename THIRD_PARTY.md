# Third-party register

| Asset/component | Version/source | License | Use/status |
|---|---|---|---|
| be-more-agent code | SHA `5fb755809583c8338b1205075b2d465baa9b49ef` | MIT | retained attribution |
| upstream faces | same SHA | not independently proven | personal prototype only; exclude from public release pending review |
| upstream sounds | same SHA | not independently proven | personal prototype only; exclude from public release pending review |
| upstream `wakeword.onnx` | same SHA; phrase not verified | unknown for bundled artifact | disabled/not installed by cloud setup |
| Piper Python package | `piper-tts==1.8.0`, OHF-Voice | GPL-3.0 | local executable dependency; redistribution review required |
| `ru_RU-dmitri-medium` | rhasspy/piper-voices; dataset OHF voice-datasets | CC0 dataset | personal prototype; SHA enforced |
| `en_US-kristin-medium` | rhasspy/piper-voices; LibriVox dataset | public domain dataset | personal prototype; SHA enforced |
| BMO name/visual identity | Adventure Time / rights holders | proprietary trademark/copyright | fan prototype; no commercial/public claim |

Voice model files are not included in the source archive. The installer downloads
them from their exact upstream URLs and verifies the SHA256 values defined in
`bmo/assets.py`.

