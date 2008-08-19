"""
The class PyTypeObject generates a PyTypeObject structure contents.
"""

class PyTypeObject(object):
    TEMPLATE = (
        'PyTypeObject %(typestruct)s = {\n'
        '    PyObject_HEAD_INIT(NULL)\n'
        '    0,                                 /* ob_size */\n'
        '    (char *) "%(tp_name)s",            /* tp_name */\n'
        '    %(tp_basicsize)s,                  /* tp_basicsize */\n'
        '    0,                                 /* tp_itemsize */\n'
        '    /* methods */\n'
        '    (destructor)%(tp_dealloc)s,        /* tp_dealloc */\n'
        '    (printfunc)0,                      /* tp_print */\n'
        '    (getattrfunc)%(tp_getattr)s,       /* tp_getattr */\n'
        '    (setattrfunc)%(tp_setattr)s,       /* tp_setattr */\n'
        '    (cmpfunc)%(tp_compare)s,           /* tp_compare */\n'
        '    (reprfunc)%(tp_repr)s,             /* tp_repr */\n'
        '    (PyNumberMethods*)%(tp_as_number)s,     /* tp_as_number */\n'
        '    (PySequenceMethods*)%(tp_as_sequence)s, /* tp_as_sequence */\n'
        '    (PyMappingMethods*)%(tp_as_mapping)s,   /* tp_as_mapping */\n'
        '    (hashfunc)%(tp_hash)s,             /* tp_hash */\n'
        '    (ternaryfunc)%(tp_call)s,          /* tp_call */\n'
        '    (reprfunc)%(tp_str)s,              /* tp_str */\n'
        '    (getattrofunc)%(tp_getattro)s,     /* tp_getattro */\n'
        '    (setattrofunc)%(tp_setattro)s,     /* tp_setattro */\n'
        '    (PyBufferProcs*)%(tp_as_buffer)s,  /* tp_as_buffer */\n'
        '    %(tp_flags)s,                      /* tp_flags */\n'
        '    %(tp_doc)s,                        /* Documentation string */\n'
        '    (traverseproc)%(tp_traverse)s,     /* tp_traverse */\n'
        '    (inquiry)%(tp_clear)s,             /* tp_clear */\n'
        '    (richcmpfunc)%(tp_richcompare)s,   /* tp_richcompare */\n'
        '    %(tp_weaklistoffset)s,             /* tp_weaklistoffset */\n'
        '    (getiterfunc)%(tp_iter)s,          /* tp_iter */\n'
        '    (iternextfunc)%(tp_iternext)s,     /* tp_iternext */\n'
        '    (struct PyMethodDef*)%(tp_methods)s, /* tp_methods */\n'
        '    (struct PyMemberDef*)0,              /* tp_members */\n'
        '    %(tp_getset)s,                     /* tp_getset */\n'
        '    NULL,                              /* tp_base */\n'
        '    NULL,                              /* tp_dict */\n'
        '    (descrgetfunc)%(tp_descr_get)s,    /* tp_descr_get */\n'
        '    (descrsetfunc)%(tp_descr_set)s,    /* tp_descr_set */\n'
        '    %(tp_dictoffset)s,                 /* tp_dictoffset */\n'
        '    (initproc)%(tp_init)s,             /* tp_init */\n'
        '    (allocfunc)%(tp_alloc)s,           /* tp_alloc */\n'
        '    (newfunc)%(tp_new)s,               /* tp_new */\n'
        '    (freefunc)%(tp_free)s,             /* tp_free */\n'
        '    (inquiry)%(tp_is_gc)s,             /* tp_is_gc */\n'
        '    NULL,                              /* tp_bases */\n'
        '    NULL,                              /* tp_mro */\n'
        '    NULL,                              /* tp_cache */\n'
        '    NULL,                              /* tp_subclasses */\n'
        '    NULL,                              /* tp_weaklist */\n'
        '    (destructor) NULL                  /* tp_del */\n'
        '};\n'
        )

    def __init__(self):
        self.slots = {}

    def generate(self, code_sink):
        """
        Generates the type structure.  All slots are optional except
        'tp_name', 'tp_basicsize', and the pseudo-slot 'typestruct'.
        """

        slots = dict(self.slots)

        slots.setdefault('tp_dealloc', 'NULL')
        slots.setdefault('tp_getattr', 'NULL')
        slots.setdefault('tp_setattr', 'NULL')
        slots.setdefault('tp_compare', 'NULL')
        slots.setdefault('tp_repr', 'NULL')
        slots.setdefault('tp_as_number', 'NULL')
        slots.setdefault('tp_as_sequence', 'NULL')
        slots.setdefault('tp_as_mapping', 'NULL')
        slots.setdefault('tp_hash', 'NULL')
        slots.setdefault('tp_call', 'NULL')
        slots.setdefault('tp_str', 'NULL')
        slots.setdefault('tp_getattro', 'NULL')
        slots.setdefault('tp_setattro', 'NULL')
        slots.setdefault('tp_as_buffer', 'NULL')
        slots.setdefault('tp_flags', 'Py_TPFLAGS_DEFAULT')
        slots.setdefault('tp_doc', 'NULL')
        slots.setdefault('tp_traverse', 'NULL')
        slots.setdefault('tp_clear', 'NULL')
        slots.setdefault('tp_richcompare', 'NULL')
        slots.setdefault('tp_weaklistoffset', '0')
        slots.setdefault('tp_iter', 'NULL')
        slots.setdefault('tp_iternext', 'NULL')
        slots.setdefault('tp_methods', 'NULL')
        slots.setdefault('tp_getset', 'NULL')
        slots.setdefault('tp_descr_get', 'NULL')
        slots.setdefault('tp_descr_set', 'NULL')
        slots.setdefault('tp_dictoffset', '0')
        slots.setdefault('tp_init', 'NULL')
        slots.setdefault('tp_alloc', 'PyType_GenericAlloc')
        slots.setdefault('tp_new', 'PyType_GenericNew')
        slots.setdefault('tp_free', '0')
        slots.setdefault('tp_is_gc', 'NULL')
        
        code_sink.writeln(self.TEMPLATE % slots)
