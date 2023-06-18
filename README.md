<p align="center">
<img src="https://drive.google.com/uc?id=1pMUqyvgMkhGYoLz3jBibZDl3J63HEcCC">
</p>

# <u>A</u>synchronous <u>C</u>omponent <u>B</u>ase

[![Code style: crackerjack](https://img.shields.io/badge/code%20style-crackerjack-000042)](https://github.com/lesleslie/crackerjack)


Asynchronous Component Base, or 'acb', is a collection of modular
components (actions / adapters) that provide the building blocks for rapid,
asynchronous, application development.
This codebase should be considered alpha right now as it is under
heavy development. A majority of the components though should be
immediately usable as they are added.

More documentation is on the way!

## Installation

```
pdm add acb
```

## Actions

### Encode

```
from acb.encode import load

load.json(obj)
```

### Hash

```
from acb.hash import hash

hash.blake2b(obj)
```

### Configure

```
from acb.configure import (
    AppConfig,
    AppSettings,
)
```

## Adapters


## Acknowledgements


## License

BSD-3-Clause
