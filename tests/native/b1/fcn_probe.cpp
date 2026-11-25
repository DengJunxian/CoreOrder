// SPDX-License-Identifier: EPL-1.0
// Numerical expression adapted from PAMS FCNAgent.submit_orders_by_market,
// masanorihirano/pams commit 6cd53810103780770c5b5d6ee0069ccab9f4b358.
// CoreOrder research feasibility probe, 2026-11-25; not the final implementation.
// The accompanying LICENSE is the unmodified upstream Eclipse Public License 1.0.
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <taskflow/taskflow.hpp>
#include <taskflow/algorithm/for_each.hpp>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <stdexcept>
#include <vector>
namespace py=pybind11;

// Columns: accessible,current,fundamental,past,time,window,mean_reversion,
// fundamental_weight,chart_weight,noise_weight,noise_scale,chart_sign,
// margin_type,order_margin,noise_draw,margin_draw.
static void one(const double* x, double* y) {
    for (int k=0;k<5;++k) y[k]=0.0;
    if (x[0]==0.0) return;
    double tw=std::min(x[4],x[5]);
    double fundamental_scale=1.0/std::max(x[6],1.0);
    double fundamental_log_return=fundamental_scale*std::log(x[2]/x[1]);
    double chart_scale=1.0/std::max(tw,1.0);
    double chart_mean_log_return=chart_scale*std::log(x[1]/x[3]);
    double noise_log_return=x[10]*x[14];
    double expected_log_return=(1.0/(x[7]+x[8]+x[9]))*
        (x[7]*fundamental_log_return+x[8]*chart_mean_log_return*x[11]+x[9]*noise_log_return);
    double expected_future_price=x[1]*std::exp(expected_log_return*x[5]);
    y[4]=expected_future_price;
    double side=(expected_future_price>x[1])?1.0:((expected_future_price<x[1])?-1.0:0.0);
    double order_price=0.0;
    if(x[12]==0.0) {
        if(side==1.0) order_price=expected_future_price*(1.0-x[13]);
        if(side==-1.0) order_price=expected_future_price*(1.0+x[13]);
    } else {
        order_price=expected_future_price+x[15]*x[13];
    }
    if(side!=0.0) {
        y[0]=side; y[1]=order_price; y[2]=1.0; y[3]=x[5];
    }
}

py::array_t<double> evaluate(py::array_t<double,py::array::c_style> input,size_t workers,const std::string& schedule) {
    if(workers==0) throw std::invalid_argument("workers must be positive");
    if(schedule!="serial" && schedule!="static" && schedule!="dynamic") throw std::invalid_argument("invalid schedule");
    auto b=input.request();
    if(b.ndim!=2 || b.shape[1]!=16) throw std::invalid_argument("expected N x 16 input");
    size_t n=static_cast<size_t>(b.shape[0]);
    std::vector<double> owned(n*16);
    if(n) std::memcpy(owned.data(),b.ptr,n*16*sizeof(double));
    py::array_t<double> result({static_cast<py::ssize_t>(n),py::ssize_t(5)});
    double* out=result.mutable_data();
    {
        py::gil_scoped_release release;
        if(schedule=="serial") {
            for(size_t i=0;i<n;++i) one(owned.data()+16*i,out+5*i);
        } else {
            tf::Executor executor(workers);
            tf::Taskflow flow;
            auto f=[&](size_t i){one(owned.data()+16*i,out+5*i);};
            if(schedule=="static") flow.for_each_index(size_t(0),n,size_t(1),f,tf::StaticPartitioner{});
            else flow.for_each_index(size_t(0),n,size_t(1),f,tf::DynamicPartitioner{64});
            executor.run(flow).get();
        }
    }
    return result;
}
PYBIND11_MODULE(fcn_probe,m){m.def("evaluate",&evaluate);}
