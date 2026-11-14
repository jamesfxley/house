# Architecture

The platform is pinned once under `@PLATFORM@`, with one standard pin beneath
it. Extensions use only the platform public API. The
[usage guide](usage-guide.md) points to configuration and tool preparation.

## Layers

The modules, their dependencies and the boundaries between them belong here.

## Service model

The call sequence, execution contexts and state ownership belong here.

## Allocation

Storage ownership and allocation behaviour belong here.

## Boundaries

The division of responsibility between the library and its callers belongs here.
