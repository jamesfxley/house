# Markdown review checklist

Read the pinned [documentation rules](../../../standard/engineering/03-documentation.md)
and [documentation review](../documentation.md).

1. Check every changed claim against its authoritative owner: implementation
   for current behavior, specification for commitments, official documentation
   for external API or protocol behavior. Mark unsupported behavior UNCONFIRMED.
2. Resolve relative links from the containing file at its deployed location.
   Check guide links both in the platform and under a family's platform pin.
   Render templates at the root before judging their routing paths. Do not
   substitute live URLs or symlinks for the checkout's pinned rules.
3. Validate commands, flags, paths, public names and configuration keys against
   the tree. C++ consumers use imported target names; internal exports are not
   documented as supported API. Compiled public API examples need owned harnesses.
4. Separate normative requirements, descriptive architecture and measured run
   evidence. Give each fact one owner; route rather than duplicate it. Read
   from the intended reader's entry point and check that their question is answered.
5. Check stable requirement IDs, real pass criteria and actual named tests.
   Deferrals belong in the tracker; measurements carry conditions in run records.
6. Keep shared examples synthetic, instruction files small and code fences
   balanced. Preserve no-trailer, approval, sourcing and done-means-gates rules.
   A link gate pass does not prove that a command or statement is true.
