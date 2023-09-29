<p align="center">
<img src="https://drive.google.com/uc?id=1pMUqyvgMkhGYoLz3jBibZDl3J63HEcCC">
</p>

# <u>A</u>synchronous <u>C</u>omponent <u>B</u>ase

[![Code style: crackerjack](https://img.shields.io/badge/code%20style-crackerjack-000042)](https://github.com/lesleslie/crackerjack)


Asynchronous Component Base, or 'acb', is a collection of modular
components (actions / adapters) that provide the building blocks for rapid,
asynchronous, application development.
This codebase should be considered alpha right now as it is under
heavy development. A majority of the components are currently being back-ported from
other apps and may not currently work as intended.

More documentation is on the way!

## Installation

```
pdm add acb
```

## Actions

### Encode

```
from acb.actions.encode import load

load.json(obj)
```

### Hash

```
from acb.actions.hash import hash

hash.blake2b(obj)
```

## Configuration

```
from acb.config import (
    Config,
    Settings,
)
```

## Logging

```
from acb.adapters.logger import Logger
```



## Adapters


## Acknowledgements


## License

BSD-3-Clause
