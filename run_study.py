"""Run the three-point study serially, retaining a log for each stage."""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=0)
    parser.add_argument("--project",default="readout_cell_v2",
                        help="Use a fresh project name after modifying geometry")
    args=parser.parse_args()
    state={"started":datetime.now().isoformat(),"completed":[]}
    status=ROOT/"results/study_status.json"
    def save():
        status.write_text(json.dumps(state,indent=2),encoding="utf-8")
    save()
    stages=[(200,"all"),(160,"all"),(240,"all")]
    for width,phase in stages:
        state.update(current_width=width,current_phase=phase);save()
        log=ROOT/"logs"/f"study_W{width}_{phase}.log"
        print("START",width,phase,flush=True)
        with log.open("w",encoding="utf-8") as handle:
            command=[sys.executable,"-X","utf8","-u",str(ROOT/"run_hfss.py"),
                "--phase",phase,"--width",str(width),"--port",str(args.port),
                "--project",args.project]
            result=subprocess.run(command,cwd=ROOT,stdout=handle,stderr=subprocess.STDOUT)
        if result.returncode:
            state.update(error=f"Stage failed: {width} {phase}; see {log}");save()
            raise SystemExit(result.returncode)
        state["completed"].append([width,phase]);save()
        print("DONE",width,phase,flush=True)
    state.update(finished=datetime.now().isoformat());save()


if __name__=="__main__":
    main()
