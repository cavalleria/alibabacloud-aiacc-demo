#!/usr/bin/env python

import argparse
import ncluster
import os
import time

INSTANCE_TYPE = 'ecs.gn6v-c10g1.20xlarge' # V100
NUM_GPUS = 8

ncluster.set_backend('aliyun')
parser = argparse.ArgumentParser()
parser.add_argument('--name', type=str, default='perseus-insightface-test',
                    help="name of the current run, used for machine naming and tensorboard visualization")
parser.add_argument('--machines', type=int, default=1,
                    help="how many machines to use")
args = parser.parse_args()

def main():
  start_time = time.time()
  # 1. Create infrastructure
  supported_regions = ['cn-huhehaote', 'cn-zhangjiakou', 'cn-shanghai', 'cn-hangzhou', 'cn-beijing']
  assert ncluster.get_region() in supported_regions, f"required AMI {IMAGE_NAME} has only been made available in regions {supported_regions}, but your current region is {ncluster.get_region()} (set $ALYUN_DEFAULT_REGION)"
  
  job = ncluster.make_job(name=args.name,
                          run_name=f"{args.name}-{args.machines}",
                          num_tasks=args.machines,
                          instance_type=INSTANCE_TYPE)
  # 2. Upload perseus insightface code.
  job.run('yum -y install unzip')
  job.upload('insightface')
  job.run('conda activate mxnet_1.5.1.post0_cu10.0_py27')
 
  # 3. Download pretrain model and dataset.
  DATA_DIR = '/root/faces_ms1m_112x112'
  job.run('cd /root && wget -c -t 10 https://public-ai-datasets.oss-cn-huhehaote.aliyuncs.com/mxnet-deepinsight/faces_ms1m_112x112.zip  && unzip faces_ms1m_112x112.zip') 

  # 4. install requirements.
  job.run('cd /root/insightface/src')
  job.run('pip install -r requirements.txt')
  
  # 5. Run the training job.
  hosts = [task.ip + f':{NUM_GPUS}' for task in job.tasks]
  host_str = ','.join(hosts)

  mpi_cmd = ['mpirun --allow-run-as-root',
            f'-np {args.machines * NUM_GPUS}',
            f'--npernode {NUM_GPUS}',
            f'--host {host_str}',
            '--bind-to none',
            '-x NCCL_DEBUG=INFO',
            '-x PATH',
            '-x LD_LIBRARY_PATH',]

  insightface_cmd = './train-perseus.sh'
 
  cmd = mpi_cmd 
  cmd = " ".join(cmd) + " " + insightface_cmd
  job.tasks[0].run(f'echo {cmd} > {job.logdir}/task-cmd')
  job.tasks[0].run(cmd, non_blocking=True)
  print(f"Logging to {job.logdir}")

  eclapse_time = time.time() - start_time
  print(f'training deploy time is: {eclapse_time} s.')


if __name__ == '__main__':
  main()

