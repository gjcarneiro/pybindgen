## -*- python -*-

def configure(conf):
    pass

def build(bld):

    #
    # PyBindGen
    #
    gen = bld.new_task_gen(
        features='command',
        source='testapi-pybindgen.py',
        target='testapimodule.cc',
        command='${PYTHON} ${SRC[0]} > ${TGT[0]}')

    obj = bld.new_task_gen('cxx', 'shlib', 'pyext')
    obj.source = [
        'testapi.cc',
        'testapimodule.cc'
        ]
    obj.target = 'testapi_pybindgen'
    obj.install_path = None # do not install
    obj.includes = '.'


    #
    # Boost::Python
    #
    obj = bld.new_task_gen('cxx', 'shlib', 'pyext')
    obj.source = [
        'testapi.cc',
        'testapi_boost.cc'
        ]
    obj.target = 'testapi_boost'
    obj.install_path = None # do not install
    obj.includes = '.'
    obj.env.append_value('LIB', 'boost_python-mt')


    #
    # SWIG
    #

    gen = bld.new_task_gen(
        features='command',
        source='testapi_swig.i',
        target='testapi_swig_module.cc',
        command='swig  -c++ -o ${TGT[0]} -python ${SRC[0]}')

    obj = bld.new_task_gen('cxx', 'shlib', 'pyext')
    obj.source = [
        'testapi.cc',
        'testapi_swig_module.cc'
        ]
    obj.target = '_testapi_swig'
    obj.install_path = None # do not install
    obj.includes = '.'
    

    #
    # SIP
    #
    gen = bld.new_task_gen(
        features='command',
        source='testapi.sip',
        target='sipAPItestapi_sip.h  siptestapi_sipcmodule.cpp  siptestapi_sipMultiplier.cpp',
        command='sip -c default/benchmarks ${SRC[0]}')

    obj = bld.new_task_gen('cxx', 'shlib', 'pyext')
    obj.source = [
        'testapi.cc',
        'siptestapi_sipcmodule.cpp',
        'siptestapi_sipMultiplier.cpp',
        ]
    obj.target = 'testapi_sip'
    obj.install_path = None # do not install
    obj.includes = '.'

    # SIP does not like -fvisibility=hidden :-(
    l = list(obj.env['CXXFLAGS_PYEXT'])
    l.remove("-fvisibility=hidden")
    obj.env['CXXFLAGS_PYEXT'] = l
