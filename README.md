# norma
This repository contains the code associated with the paper "LLM based Normative MAS for Scientific Collaboration"

## Norm lifecycle

Norms are evaluated over the evolving state of the sociotechnical system. When
an agent considers an action, the Norm Evaluator identifies norms applicable to
the current state and simulates the candidate action to determine whether it
would satisfy or violate those norms. The evaluator retains relevant state and
action history across logical interaction steps, allowing conditions that unfold
over time to use prior events. A norm situation progresses as its antecedent
becomes true, its discharge condition is satisfied, or its violation condition
is detected. Violations are passed to Org, which applies the matching policy
sanctions.
