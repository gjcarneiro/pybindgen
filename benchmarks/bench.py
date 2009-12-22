
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'build', 'default', 'benchmarks'))

from timeit import Timer

TIMES = 10000000



def bench(mod):
    def bench3():
        return mod.Multiplier()
    print "test3 (call class constructor with no arguments):", Timer(bench3).timeit(TIMES)

    def bench4():
        return mod.Multiplier(3.0)
    print "test4 (call class constructor with double):", Timer(bench4).timeit(TIMES)

    obj = mod.Multiplier(3.0)
    def bench5():
        return obj.GetFactor()
    print "test4 (call method with no arguments):", Timer(bench5).timeit(TIMES)

    obj = mod.Multiplier(3.0)
    def bench6():
        return obj.Multiply(5.0)
    print "test4 (call method with double):", Timer(bench6).timeit(TIMES)

    def bench1():
        return mod.func1()
    print "test1 (call function with no arguments):", Timer(bench1).timeit(TIMES)
    
    def bench2():
        return mod.func2(1.0, 2.0, 3.0)
    print "test2 (call function taking 3 doubles):", Timer(bench2).timeit(TIMES)


def main():
    import testapi_pybindgen
    import testapi_boost
    import testapi_swig

    print "pybindgen results:"
    bench(testapi_pybindgen)

    print "boost_python results:"
    bench(testapi_boost)

    print "swig results:"
    bench(testapi_swig)


if __name__ == '__main__':
    main()
