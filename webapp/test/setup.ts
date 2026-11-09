// Testing Library unmounts rendered trees between tests only when Vitest
// exposes globals; this project keeps imports explicit, so the cleanup is
// registered here for every test file (vitest.config.mts `setupFiles`).
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());
