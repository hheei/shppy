#!/bin/bash
#SBATCH --job-name=UNK-JOB
#SBATCH --partition=normal_lmxu
#SBATCH --nodes=4
#SBATCH --ntasks=128
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=7700M
#SBATCH --time=12-00:00:00
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.err
if [ -z "${SLURM_JOB_ID}" ]; then
    echo "\${SLURM_JOB_ID} is not set."
    echo "Either \`sbatch job.sh\` or \`bash sub.sh\` to submit the job."
    exit 1
fi

source ~/.bashrc
module purge
cd ${SLURM_SUBMIT_DIR}
scck job init

module add qe/7.5

ulimit -Ss unlimited
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK}

# mpirun -np ${SLURM_NTASKS} pw.x -in scf.in
mpirun -np ${SLURM_NTASKS} pw.x -nt 4 -nd 4 -in pw.1.in