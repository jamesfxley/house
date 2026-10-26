# Machinery cost review

For each mechanism touched, state the concrete consumer failure it prevents,
the recurring cost per change or release, and whether ordinary review would
notice the drift anyway. A consumer or a checker having fired is insufficient
justification. Certainty has a cost even when detection is already covered.

Give every priced item one verdict:

- `keep`: clears the test; say why it stays.
- `simplify`: name a cheaper mechanism for the same drift and its recurring cost
  difference. Consider this first.
- `remove`: name the protection knowingly given up; obtain approval before removal.
- `defer`: identify the concrete blocker, cost and destination for follow-up.
  Creating or editing its tracker entry still needs specific approval.

Consider removal or folding before strengthening. Added entry points,
declaration files, gates, flags and cross-repository transactions must retire
at least as much contributor knowledge as they add. Add machinery only for an
observed failure or a failure made inevitable by the repository's structure;
a hypothetical risk does not justify a new checker.

Justify what stays. Price recurring work rather than sunk setup or line counts.
If removal costs more than living with a mechanism, say so. Do not replace a
checker with an unpriced promise to remember; accept lost protection explicitly.
An item you cannot confidently rule on is not a finding. Every reported item
has both price and verdict; keep the report short enough to act on.
