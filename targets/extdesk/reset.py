"""Reset ExtDesk (the SIMULATOR) to its exact seeded state."""
import os

import seed as seed_module

if __name__ == "__main__":
    if os.path.exists(seed_module.DB_PATH):
        os.remove(seed_module.DB_PATH)
    n = seed_module.seed(seed_module.DB_PATH)
    print(f"extdesk reset: {n} issues -> {seed_module.DB_PATH}")
