import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from substrate import SanctionDecision, SanctionType, ViolationEvent


@dataclass(frozen=True)
class SanctionRule:
    # Rules are checked in order; the first matching rule may emit multiple
    # sanctions for one violation event.
    when: Callable[[ViolationEvent], bool]
    sanctions: tuple[SanctionType, ...]


class OrgSelf:
    def __init__(
        self,
        policy: Mapping[str, SanctionType | list[SanctionType] | tuple[SanctionType, ...] | list[SanctionRule]],
        clock: Callable[[], int] | None = None,
    ):
        # A simple SanctionType remains valid for unconditional one-sanction
        # policies; lists and SanctionRule values support richer scenarios.
        self.policy = dict(policy)
        self.clock = clock or (lambda: int(time.time()))
        self._processed_violations: set[int] = set()

    def get_possible_sanctions(self) -> list[str]:
        sanctions = []
        for policy_value in self.policy.values():
            if isinstance(policy_value, SanctionType):
                values = [policy_value]
            elif policy_value and isinstance(policy_value[0], SanctionRule):
                values = [sanction for rule in policy_value for sanction in rule.sanctions]
            else:
                values = list(policy_value)
            sanctions.extend(sanction.value for sanction in values)
        return list(dict.fromkeys(sanctions))

    def respond(self, violation: ViolationEvent) -> SanctionDecision | list[SanctionDecision] | None:
        decisions = self.respond_all(violation)
        if len(decisions) == 1:
            return decisions[0]
        return decisions or None

    def respond_all(self, violation: ViolationEvent) -> list[SanctionDecision]:
        # Violation IDs make repeated evaluation idempotent within an episode.
        if violation.violation_id in self._processed_violations:
            return []
        self._processed_violations.add(violation.violation_id)

        policy_value = self.policy.get(violation.norm_id)
        if policy_value is None:
            return []
        if isinstance(policy_value, SanctionType):
            sanctions = [policy_value]
        elif policy_value and isinstance(policy_value[0], SanctionRule):
            matching_rule = next((rule for rule in policy_value if rule.when(violation)), None)
            sanctions = list(matching_rule.sanctions) if matching_rule else []
        else:
            sanctions = list(policy_value)

        return [
            SanctionDecision(
                violation_id=violation.violation_id,
                subject=violation.subject,
                sanction=sanction,
                object=violation.object,
                reason=f"Policy for norm {violation.norm_id} imposes a {sanction.value}.",
                timestamp=self.clock(),
            )
            for sanction in sanctions
        ]