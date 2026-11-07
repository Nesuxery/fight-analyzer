"""Worker entry point: python -m fight_analyzer.jobs

Kept separate from worker.py on purpose: running worker.py itself as
__main__ would load it twice, and pipeline stages would raise a JobFailed
class the running worker does not recognise.
"""

from fight_analyzer.jobs.worker import main

main()
