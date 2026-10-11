# Preserved incomplete controller launch

The controller stopped after its second child on `assert child.returncode == 0`.
The child had disappeared between poll() and psutil.memory_info(), and the
exception branch did not call wait() to populate the exit code. There were no
logged child exceptions. The first JSON was finalized; the second remains
the original worker output. Neither was removed or changed.

The complete comparison restarts the same schedule in `scale-20261011-v2`
after an unconditional wait() was added to the controller. No algorithm or
dataset changes. This partial run is excluded from aggregate results.
