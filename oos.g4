grammar oos;

@header{dollar = '$'}

startRule
        :   classes
        ;

classes
        :   class_def*
            class_main_def
            EOF
        ;

// CHANGES IN COMMENTS SPECIFIED BELOW: 
// labeled class names
// created list of inherited classes to find in listener (inherited)
// add all possible inherited class names to inherited
// return inherited so it can be referenced at all
class_def returns [list inherited]
        :   'class' cl_n1=class_name {$inherited = []}
            ( 'inherits' cl_n2=class_name {$inherited.append($cl_n2.cl_n)}
            (',' cl_n2=class_name {$inherited.append($cl_n2.cl_n)} )*  )? ':'
            decl = declarations
            class_body
        ;

class_main_def
        :   'class' ('main' | 'Main') ':'
            decl = declarations
            main_body
        ;

// class_name now returns a string of the class name text
class_name returns [string cl_n]
        : ID {$cl_n = $ID.text}
        ;

// declarations now returns decl : a list of lists of strings (each sub-list is a declaration line)
declarations returns [list decl]
        :   {$decl = []}
            (dl=decl_line {$decl.append($dl.fields)}
            (';' dl=decl_line {$decl.append($dl.fields)})* ';' ';')?
        ;

class_body
        :   (constructor_def ';'';')+
            (method_def ';'';')*
        ;

main_body
        :   method_main_def ';'';'
        ;

// decl_line now returns a list of strings with:
// a string t, the type of the fields in decl_line at index 0
// the names of the fields
decl_line returns [list fields]
        :   t=types {$fields = [$t.text]}
            a=ID {$fields.append($a.text)}
            (',' a=ID {$fields.append($a.text)} )*
        ;

// labeled parameters, class_name and declarations for use in listener
constructor_def
        :   'def' '__init__' plist=parameters ':' cl=class_name
            decl=declarations
            method_body
        ;

// label function name, parameters, and return type with indicative labels
method_def
        :   'def' funcname=ID plist=parameters ':' (typeint='int' | voidtype='-' | cl_n=class_name)
            decl=declarations
            method_body
        ;

method_main_def
        :   'def' 'main' '(' 'self' ')' ':' '-'
            decl = declarations
            method_body
        ;

// types returns what it read as t
types returns [string t]
        :   cn=class_name {$t = $cn.cl_n}
        |   'int' {$t = 'int'}
        ;

// parameters gives what it got from parlist
parameters returns [list plist]
        :   '(' pl=parlist {$plist = $pl.pl} ')'
        ;

// declarations labeled
method_body
        :   decl=declarations
            (statements )?
        ;

return_type
        :   types
        |   '-'
        ;

// returns a list of parameters
// as list of strings
// empty if no parameters
// otherwise it's [<type>, <field>, ...]
parlist returns [list pl]
        :   'self' {$pl = []}
            (',' t=types {$pl.append($t.t)}
            field=ID {$pl.append($field.text)} )*
        ;

statements :   statement (';' statement )*
        ;

// labels added, prints for statements in listener
statement
        :   assign=assignment_stat
        |   direct=direct_call_stat
        |   if_stat
        |   while_stat
        |   ret=return_stat
        |   inputs=input_stat
        |   prints=print_stat
        ;

// can't handle code generation here with constructor call
// if s is empty, handle finding cl_n in symTable and generating appropriate code in listener
// if s is not empty, handle it the same way as the other simple statements
assignment_stat returns [string s]
        :   {$s = ''} ('self.' {$s += f"{dollar}temp->"})? ID {$s += $ID.text + '='} '=' 
            ( exp=expression {$s += $exp.exp + ';\n'} |   cc = constructor_call )
        ;

// code copied from factor, with slight changes
// generate code in listener based on this
direct_call_stat returns [list f]
        :   (self = 'self.')? idd = ID '.' func = func_call
            {args = [arg + ', ' for arg in $func.fcall[1]]}
            {if $self.text == 'self':}
            {       $f = ['4'] + $func.fcall[0] + ['('] + args + [f"&({dollar}temp->"] + [$idd.text] + ['))']}
            {else:}
            {       $f = ['4'] + $func.fcall[0] + ['('] + args + ['&'] + [$idd.text] + [')']}
        |   'self.' func = func_call
            {args = [arg + ', ' for arg in $func.fcall[1]]}
            {$f = ['5'] + $func.fcall[0] + ['('] + args + [f"{dollar}temp"] + [')']}
        ;

// handled in listener
if_stat
        :   'if' '(' cond = condition ')' ':'
            (statements ';' )?
            else_part
            'endif'
        ;

// handled entirely on listener
else_part
        :   'else' ':'
            ( statements ';' )?
        |
        ;

// code generation on listener, or sub-statements
while_stat
        :   'while' '(' cond=condition ')' ':'
            ( statements )?
            'endwhile'
        ;

// return stat returns either contents of pointer of struct instance representing current class,
// a field of current class,
// or code for an expression 
return_stat returns [string s]
        :   'return' {$s = 'return '} ( 'self' {$s += f"*{dollar}temp;\n"}
        |   'self.' ID {$s += f"{dollar}temp->"+ $ID.text + ';\n'}
        |   exp=expression {$s += $exp.exp + ';\n'} )
        ;

// return string of statement
// note that if self, reference is made to pointer of struct instance
input_stat returns [string s]
        :   'input' {$s= 'scanf("%d", &'} ('self.' {$s += f"{dollar}temp->"})? ID {$s += $ID.text + ');\n'}
        ;

// s will be the string to be printed and a newline print
// -- I don't get why mutliple ';' characters are needed, but sure ok
print_stat returns [string s]
        :   'print' exp=expression {$s = 'printf("%d",' + $exp.exp + ');;\n'} (',' exp=expression {$s += 'printf(", %d",' + $exp.exp + ');;\n'})*
        ;

// return a string of the expression exp
expression returns [string exp]
        :   o=optional_sign {$exp=$o.o} t=term {$exp+=$t.t} (a=add_oper {$exp+=$a.a} t=term {$exp+=$t.t})*
        ;

// arguments returns list from arglist
arguments returns [list args]
        :   '(' argl=arglist {$args = $argl.argl} ')'
        ;

// string of condition
condition returns [string cond]
        :   bt=boolterm {$cond = $bt.bt} ('or' bt=boolterm {$cond+= '||' + $bt.bt} )*
        ;

// optional_sign returns blank string or add_oper
optional_sign returns [string o]
        :   a=add_oper {$o = $a.a}
        |   {$o = ''}
        ;

// term returns a string representation of the term
term returns [string t]
        :   f=factor {$t = ''.join($f.f[1:])} ( m=mul_oper {$t+=$m.m} f=factor {$t += ''.join($f.f[1:])} )*
        ;

// add_oper returns string of the operator
add_oper returns [string a]
        :   '+' {$a = '+'}
        |   '-' {$a = '-'}
        ;

// arglist is either an empty list of list of arguments
arglist returns [list argl]
        :   {$argl = []} arg=argitem {$argl.append($arg.arg)} (',' arg=argitem {$argl.append($arg.arg)})*
        |   {$argl = []}
        ;

// string of boolterm
boolterm returns [string bt]
        :   bf=boolfactor {$bt=$bf.bf} ( 'and' bf=boolfactor {$bt+= '&&' + $bf.bf})*
        ;

// returns list of strings of what is to be printed
// dollar signs need to be string literals to not confuse with antlr specifics
// first element is option of factor, important for checking in listener
// this list HAS to be concatenated in term (without first element)
// also change the fact that to call function, needs to be called as self.func
factor returns [list f]
        :   {$f=['1']} i=INTEGER {$f+=[$i.text]}
        |   {$f=['2']} '(' e=expression ')' {$f+= ['('] + [$e.exp] +[')']}
        |   {$f=['3']} ('self.' {$f+= [f"{dollar}temp->"]})? idd=ID {$f+=[$idd.text]}
        |   {$f=['4']} (self='self.')? idd=ID '.' func=func_call
            {args = [arg + ', ' for arg in $func.fcall[1]]}
            {if $self:}
            {       $f += $func.fcall[0] + ['('] + args + [f"&({dollar}temp->"] + [$idd.text] + ['))']}
            {else:}
            {       $f += $func.fcall[0] + ['('] + args + ['&'] + [$idd.text] + [')']}
        |   {$f=['5']} self='self.' func=func_call
            {args = [arg + ', ' for arg in $func.fcall[1]]}
            {$f += $func.fcall[0] + ['('] + args + [f"{dollar}temp"] + [')']}
        |   {$f=['6']} classname=ID.field=ID {$f+=[$classname.text] + ['.'] + [$field.text]}
        |   {$f=['7']} field=ID {$f+=[$field.text]}
        ;

// mul_oper returns string of the operator
mul_oper returns [string m]
        :   '*' {$m = '*'}
        |   '/' {$m = '/'}
        ;

// argitem returns a string of the expression as argument
argitem returns [string arg]
        :   exp=expression {$arg = $exp.exp}
        ;

// return the string to print
// expressions are going to be in parentheses, C might be slightly finicky else
boolfactor returns [string bf]
        :   'not' '[' cond=condition ']' {$bf = '!(' + $cond.cond + ')'}
        |   '[' cond=condition ']' {$bf = '(' + $cond.cond + ')'}
        |   exp1=expression rel=rel_oper exp2=expression {$bf='('+ $exp1.exp + ')' + $rel.ro + '(' + $exp2.exp + ')'}
        ;

// index 0 is function name
// index 1 is arguments of function call
func_call returns [list fcall]
        :   ID {$fcall = [[$ID.text]]} args=arguments {$fcall.append($args.args)}
        ;

// return a list: [<class name>, <arguments>]
// and based on those then generate code
constructor_call returns [list cc]
        :   cl_n=class_name
            args=arguments
            {$cc = [$cl_n.cl_n] + $args.args}
        ;

// return the string
rel_oper returns [string ro]
        :   '==' {$ro = '=='}
        |   '<=' {$ro = '<='}
        |   '>=' {$ro = '>='}
        |   '>' {$ro = '>'}
        |   '<' {$ro = '<'}
        |   '!=' {$ro = '!='}
        ;

//------------------------------------------------------------------------------
//------------------------------------------------------------------------------

WS: [ \t\r\n]+ -> skip;
COMMENTS: '#' ~[#]* '#' -> skip;
ID: ID_START (ID_CONTINUE)*;
INTEGER: NON_ZERO_DIGIT (DIGIT)* | '0'+;


fragment ID_START
        : [A-Z]
        | [a-z]
        ;

fragment ID_CONTINUE
        : '_'
        | [A-Z]
        | [a-z]
        | [0-9]
        ;


fragment NON_ZERO_DIGIT
        : [1-9]
        ;

fragment DIGIT
        : [0-9]
        ;
