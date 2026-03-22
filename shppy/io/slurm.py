from pathlib import Path
from typing import Any
from dataclasses import dataclass, field


@dataclass
class Job:
    sbatch_params: dict[str, Any] = field(default_factory=dict)

    init_script: list[str] = [
        'if [ -z "${SLURM_JOB_ID}" ]; then',
        '  echo "\${SLURM_JOB_ID} is not set."',
        '  echo "Use `sbatch job.sh` to submit the job."',
        "  return 0 2>/dev/null || exit 0",
        "fi",
        "export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}",
        ". ~/.bashrc && module purge && cd ${SLURM_SUBMIT_DIR} && scck job init",
    ]

    opt_script: list[str] = ["# ulimit -Ss unlimited"]

    run_script: list[str] = ["# mpirun -np ${SLURM_NTASKS} ..."]

    @classmethod
    def read(cls, path):
        path = Path(path).expanduser().resolve()

        lines = path.read_text().splitlines()
        scripts = {"init": [], "opt": [], "run": []}
        this = "init"
        sbatch_params = {}
        for line in lines:
            if line.startswith("#SBATCH"):
                k, v = line[8:].split("=", 1)
                sbatch_params[k.strip()] = v.strip()
            elif line.startswith("## Initialize script"):
                this = "init"
            elif line.startswith("## Optional Script"):
                this = "opt"
            elif line.startswith("## Run Script"):
                this = "run"
            else:
                scripts[this].append(line)

        return cls(sbatch_params, scripts["init"], scripts["opt"], scripts["run"])

    def write(self, path="."):
        path = Path(path).expanduser().resolve()
        with open(path, "w") as f:
            f.write("#!/bin/bash\n")
            sp = self.sbatch_params
            f.write(f"#SBATCH --job-name={sp.get('job-name', 'ShppyJob')}\n")
            f.write(f"#SBATCH --partition={sp.get('partition', '')}\n")
            f.write(f"#SBATCH --time={sp.get('time', '')}\n")
            f.write(f"#SBATCH --mem-per-cpu={sp.get('mem-per-cpu', '')}\n")
            f.write(f"#SBATCH --nodes={sp.get('nodes', '1')}\n")
            f.write(f"#SBATCH --ntasks-per-node={sp.get('ntasks-per-node', '')}\n")
            f.write(f"#SBATCH --cpus-per-task={sp.get('cpus-per-task', '')}\n")
            f.write(f"#SBATCH --gpus-per-task={sp.get('gpus-per-task', '')}\n")
            f.write(f"#SBATCH --output={sp.get('output', 'slurm-%j.out')}\n")
            f.write(f"#SBATCH --error={sp.get('error', 'slurm-%j.err')}\n")
            f.write(f"#SBATCH --export={sp.get('export', 'ALL')}\n")
            f.write("\n")
            f.write("## Initialize script\n")
            for line in self.init_script:
                f.write(line + "\n")
            f.write("\n")
            f.write("## Optional Script\n")
            for line in self.opt_script:
                f.write(line + "\n")
            f.write("\n")
            f.write("## Run Script\n")
            for line in self.run_script:
                f.write(line + "\n")
            f.write("\n")
