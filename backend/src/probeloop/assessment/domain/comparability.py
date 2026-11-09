"""Target expectations form part of the assessment policy, not candidate evidence."""

import hashlib
import json

from probeloop.context.domain.model import RoleProfile


def assessment_profile_id(profile: RoleProfile | None, policy_version: str | None) -> str | None:
    if profile is None or policy_version is None:
        return None

    def text(value: str) -> str:
        return " ".join(value.casefold().split())

    content = {
        "policy": policy_version,
        "profession": text(profile.profession),
        "role": text(profile.target_role),
        "level": text(profile.seniority),
        "responsibilities": sorted(text(v) for v in profile.responsibilities),
        "competencies": sorted(text(v) for v in profile.competencies),
    }
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
