# Third-party notices

ProbeLoop's [Apache-2.0 licence](LICENSE) applies to its own application code,
documentation and installation scripts. It does not relicense dependencies, model weights,
voices or fonts. [NOTICE](NOTICE) accompanies the installer and runtime images.

## Runtime software

Python and JavaScript dependencies retain their upstream licences and package notices.
Pinned versions are recorded in `backend/uv.lock`, `frontend/package-lock.json` and
`docker/tts-piper/requirements.txt`. Debian package notices remain under `/usr/share/doc` in
the images; installed Python distributions retain their licence metadata.
The frontend build collects production-package licence and notice files into
`THIRD_PARTY_LICENSES.txt`, distributed with the browser assets.
The npm archive for `react-remove-scroll-bar` 2.3.8 omits its licence file. Its MIT notice is
preserved from [the upstream licence revision](https://github.com/theKashey/react-remove-scroll-bar/blob/7301c160fda44cb8cf2b9fdfde61efad35736196/LICENSE)
in [a version-specific copy](licenses/react-remove-scroll-bar-2.3.8-MIT.txt). A dependency update
must review that notice again.

[Piper 1.8.0](https://github.com/OHF-Voice/piper1-gpl/tree/v1.8.0) is an unmodified,
separate GPL-3.0-or-later program reached over HTTP. Its GPL terms, including redistribution
and corresponding-source requirements, apply to that component. Its distribution includes
espeak-ng components; their upstream notices remain applicable. ProbeLoop does not import
Piper into its backend process. The Piper repository provides the engine source and build
instructions for this version.

## Fonts and artwork

- **Inter:** Copyright 2016 The Inter Project Authors, [upstream](https://github.com/rsms/inter).
  [Full SIL OFL 1.1 notice](licenses/inter-OFL-1.1.txt).
- **Space Grotesk:** Copyright 2020 The Space Grotesk Project Authors,
  [upstream](https://github.com/floriankarsten/space-grotesk).
  [Full SIL OFL 1.1 notice](licenses/space-grotesk-OFL-1.1.txt).
  The application wordmark and documentation SVG outlines use this font.
- **Lucide:** Icons are supplied by `lucide-react`; see its
  [ISC licence and upstream MIT notices](https://github.com/lucide-icons/lucide/blob/main/LICENSE).
- README stack badges are served by [Shields.io](https://shields.io/).
  Technology names and logos retain their owners' rights.

## Downloaded models

The runtime images and installer ZIP contain no model weights. The provisioner downloads
approved artifacts from the sources recorded in its versioned catalog. Installing a conversion
or fine-tuning does not replace the original model's applicable terms.

| Component | Attribution and terms |
|---|---|
| Parakeet TDT 0.6B v3, int8 ONNX | NVIDIA; ONNX conversion by istupakov. [Pinned model card](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx/blob/8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce/README.md), [original model](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3), CC-BY-4.0. The downloaded artifacts are converted and quantized versions. |
| Whisper large-v3-turbo conversion | [Conversion](https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo), [OpenAI model](https://huggingface.co/openai/whisper-large-v3-turbo), MIT. Optional second transcription. |
| Piper Serena voice | [Voice card](https://huggingface.co/rhasspy/piper-voices/blob/cf910fb59f1d79ab3b625a63993a108751c6c25d/it/it_IT/serena/medium/MODEL_CARD), CC-BY-4.0. Further voice credits are in [the voice guide](https://github.com/subnetMusk/probeloop/blob/main/docs/voices.md). |
| Laya stated-limit fine-tuning | ProbeLoop synthetic-data fine-tuning of ConvAI Innovations' Laya multilingual, Apache-2.0. Its underlying [mmBERT-base encoder](https://huggingface.co/jhu-clsp/mmBERT-base), by JHU-CLSP and the mmBERT authors, is identified as MIT. Retain both upstream attributions and applicable terms. [Provisional model card](https://huggingface.co/submsk/probeloop-laya-stated-limits). |

Optional Ollama models have their own model-specific licences. Their host installation and
distribution remain separate from the ProbeLoop installer.
