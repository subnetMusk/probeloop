# Piper voice credits

Piper runs as a separate program. Voice weights remain in the user's models volume and are not
redistributed with ProbeLoop.

| Voice | Use | Model card and licence |
|---|---|---|
| it_IT-serena-medium | Default Italian interviewer | [Model card](https://huggingface.co/rhasspy/piper-voices/blob/main/it/it_IT/serena/medium/MODEL_CARD), CC BY 4.0 |
| it_IT-paola-medium | Synthetic speech fixtures and optional interviewer | [Model card](https://huggingface.co/rhasspy/piper-voices/blob/main/it/it_IT/paola/medium/MODEL_CARD), CC0 |
| it_IT-riccardo-x_low | Default synthetic candidate, male voice at 16 kHz | [Model card](https://huggingface.co/rhasspy/piper-voices/blob/main/it/it_IT/riccardo/x_low/MODEL_CARD), M-AILABS dataset licence |

The riccardo model card refers to the M-AILABS speech dataset licence. Its original linked website
could not be fetched during verification. The dataset authors maintain the [licence in their repository](https://github.com/i-celeste-aurora/m-ailabs-dataset#license):
copyright 2017–2019, original creators at M-AILABS; use and redistribution, including commercial
use and modification, are permitted subject to retaining the source-data notices and avoiding
endorsement claims. The dataset is supplied without warranty. This is a summary; the linked
licence is authoritative.

For synthetic acceptance runs, download riccardo explicitly:

```bash
docker compose --profile setup run --rm tts-voices it_IT-riccardo-x_low
```

The interviewer keeps serena; pass `--voice` to `evals.voice_candidate` to select another
downloaded candidate voice. Pass `--snapshot-id` to use the approved context created in the wizard.
