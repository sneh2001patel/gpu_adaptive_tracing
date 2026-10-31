// Hardware acceptance probe: actual CUDA calls in the GPU-owning process.
#include <cuda_runtime.h>
#include <cuda_profiler_api.h>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <unistd.h>

__global__ void revision_probe(float* x, int n) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i < n) {
    float v = x[i];
    for (int j=0; j<256; ++j) v = fmaf(v, 1.000001f, 0.00001f);
    x[i] = v;
  }
}
void check(cudaError_t e) {
  if(e != cudaSuccess) { fprintf(stderr,"CUDA error: %s\n",cudaGetErrorString(e)); exit(2); }
}
void mark(const char* name, int range, int iterations) {
  auto stamp = std::chrono::steady_clock::now().time_since_epoch();
  printf("{\"event\":\"%s\",\"range\":%d,\"iterations\":%d,\"pid\":%d,\"target_clock_ns\":%lld}\n",
    name,range,iterations,getpid(),(long long)std::chrono::duration_cast<std::chrono::nanoseconds>(stamp).count());
  fflush(stdout);
}
int main() {
  float* data; int n=1<<20, iteration=0;
  check(cudaMalloc(&data,n*sizeof(float)));
  check(cudaMemset(data,0,n*sizeof(float)));
  mark("worker_ready",0,iteration);
  for(int range=1;range<=2;++range) {
    check(cudaProfilerStart()); mark("capture_start_api_returned",range,iteration);
    auto begin=std::chrono::steady_clock::now();
    while(std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count()<.4) {
      revision_probe<<<n/256,256>>>(data,n); check(cudaDeviceSynchronize()); ++iteration;
    }
    check(cudaProfilerStop()); mark("capture_stop_api_returned",range,iteration);
    begin=std::chrono::steady_clock::now();
    while(std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count()<4) {
      revision_probe<<<n/256,256>>>(data,n); check(cudaDeviceSynchronize()); ++iteration;
      if(iteration%100==0) mark("post_capture_progress",range,iteration);
      std::this_thread::sleep_for(std::chrono::milliseconds(2));
    }
  }
  check(cudaFree(data)); mark("worker_finished",2,iteration);
}
