import tokenizer

MODIFIERS = ['const', 'volatile'] # XXX: are there others?

if 'set' not in dir(__builtins__):
    # Nominal support for Python 2.3.
    from sets import Set as set


class CType(object):
    """
    A L{CType} represents a C/C++ type as a list of items.  Generally
    the items are L{Token}s, but some times they can be other
    L{CType}s (arguments of templated types, function pointer name and parameters).
    """
    __slots__ = 'tokens'
    def __init__(self):
        self.tokens = []

    def reorder_modifiers(self):
        """
        Reoder const modifiers, as rightward as possible without
        changing the meaning of the type.  I.e., move modifiers to the
        right until a * or & is found."""
        for modifier in MODIFIERS:
            self._reorder_modifier(modifier)

    def _reorder_modifier(self, modifier):
        tokens_moved = []
        while 1:
            reordered = False
            for token_i, token in enumerate(self.tokens):
                if isinstance(token, CType):
                    continue
                if token.name == modifier and token not in tokens_moved:
                    ## Reorder the token.  Note: we are mutating the
                    ## list we are iterating over, but it's ok because
                    ## we'll break the for unconditionally next.

                    self.tokens.pop(token_i)
                    
                    for new_pos in range(token_i, len(self.tokens)):
                        other_token = self.tokens[new_pos]
                        if isinstance(other_token, CType):
                            continue
                        if other_token.name in ['*', '&']:
                            self.tokens.insert(new_pos, token)
                            break
                    else:
                        self.tokens.append(token)
                        new_pos = -1

                    tokens_moved.append(token)
                    reordered = True
                    break
            if not reordered:
                break

    def remove_modifiers(self):
        """
        Remove modifiers from the toplevel type.  Return a set of modifiers removed.
        """
        retval = set()
        for modifier in MODIFIERS:
            if self._remove_modifier(modifier):
                retval.add(modifier)
        return retval

    def _remove_modifier(self, modifier):
        changed = True
        removed = False
        while changed:
            changed = False
            for token_i, token in enumerate(self.tokens):
                if isinstance(token, CType):
                    continue
                if token.name == modifier:
                    del self.tokens[token_i]
                    changed = True
                    removed = True
                    break
        return removed

    def __str__(self):
        l = []
        first = True
        for token in self.tokens:
            if isinstance(token, tokenizer.Token):
                if token.name in "<,":
                    l.append(token.name)
                else:
                    if first:
                        l.append(token.name)
                    else:
                        l.append(' ' + token.name)
            else:
                assert isinstance(token, CType)
                if first:
                    l.append(str(token))
                else:
                    l.append(' ' + str(token))
            first = False
        return ''.join(l)


def _parse_type_recursive(tokens):
    ctype = CType()
    while tokens:
        token = tokens.pop(0)
        if token.token_type == tokenizer.SYNTAX:
            if token.name in [',', '>', ')']:
                ctype.reorder_modifiers()
                return ctype, token
            elif token.name in ['<', '(']:
                ctype.tokens.append(token)
                while 1:
                    nested_ctype, last_token = _parse_type_recursive(tokens)
                    ctype.tokens.append(nested_ctype)
                    ctype.tokens.append(last_token)
                    assert token.token_type == tokenizer.SYNTAX
                    if last_token.name == ',':
                        continue
                    elif last_token.name in ['>', ')']:
                        break
                    else:
                        assert False, ("last_token invalid: %s" % last_token)
            else:
                ctype.tokens.append(token)
        else:
            ctype.tokens.append(token)
    ctype.reorder_modifiers()
    return ctype, None


def parse_type(type_string):
    """
    Parse a C type string.

    @param type_string: C type expression
    @returns: a L{CType} object representing the type
    """
    tokens = list(tokenizer.GetTokens(type_string + '\n'))
    ctype, last_token = _parse_type_recursive(tokens)
    assert last_token is None
    return ctype

def normalize_type_string(type_string):
    """
    Return a type string in a canonical format, with deterministic
    placement of modifiers and spacing.  Useful to make sure two type
    strings match regardless of small variations of representation
    that do not change the meaning.

    @param type_string: C type expression
    @returns: another string representing the same C type but in a canonical format

    >>> normalize_type_string('char *')
    'char *'
    >>> normalize_type_string('const foo::bar<const char*, zbr&>*')
    'foo::bar< char const *, zbr & > const *'
    >>> normalize_type_string('const ::bar*')
    '::bar const *'
    >>> normalize_type_string('const char*const')
    'char const * const'
    >>> normalize_type_string('const char*const*const')
    'char const * const * const'
    >>> normalize_type_string('const std::map<std::string, void (*) (int, std::vector<zbr>) >')
    'std::map< std::string, void ( * ) ( int, std::vector< zbr > ) > const'
    """
    ctype = parse_type(type_string)
    return str(ctype)

