# Asynchronus Code Base

## About

Asynchronus Code Base (acb) is a collection of core actions and adapters useful for building out applications.

## Installation

```
pdm add acb
```

## Usage

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

