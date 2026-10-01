import time
from collections.abc import Callable, Mapping

from substrate import SanctionDecision, SanctionType, ViolationEvent


class OrgSelf:
    def __init__(
        self,
        policy: Mapping[str, SanctionType],
        clock: Callable[[], int] | None = None,
    ):
        self.policy = dict(policy)
        self.clock = clock or (lambda: int(time.time()))
        self._processed_violations: set[int] = set()

    def get_possible_sanctions(self) -> list[str]:
        return list(dict.fromkeys(sanction.value for sanction in self.policy.values()))

    def respond(self, violation: ViolationEvent) -> SanctionDecision | None:
        if violation.violation_id in self._processed_violations:
            return None
        self._processed_violations.add(violation.violation_id)

        sanction = self.policy.get(violation.norm_id)
        if sanction is None:
            return None

        return SanctionDecision(
            violation_id=violation.violation_id,
            subject=violation.subject,
            sanction=sanction,
            object=violation.object,
            reason=f"Policy for norm {violation.norm_id} imposes a {sanction.value}.",
            timestamp=self.clock(),
        )