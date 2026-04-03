# OOS-to-C compiler

## About OOS

OOS (Object Oriented Simple) is a made-up language used for the purposes of learning to create a compiler from a simplified OO language to a procedural language. It's Python-like in syntax, and Java-like in behavior.

## Known possible errors and important notes

- Situations might come up, where helper function that changes function names will skip function names, namely, the first function call found in an expression. A possible fix is calling said function in a while loop, that terminates only when list `self.replaceFunctions` is empty, instead of erasing it after processing. Refer to CCodeTranslator class' fields for replaceFunctions' purpose.

## List of contents provided
- Changed grammar `oos.g4`, with added actions and couple of fixes
- A Python file containing new Listener `myoosListener.py`
- A Python file that runs all ANTLR related operations, etc. `main.py`
- Test files: `shape.oos`, `complex.oos`.
- A picture of a runtime example, `runtime_example.png`

## Runtime environment info

ANTLR4 version is 4.13.2 , downloaded through pip, as `python3 -m pip install antlr4-python3-runtime`

OS is Ubuntu 22.04.5 LTS.

## Compiling the OOS code into C

Using an Ubuntu (or generally Debian-based) terminal:

To create ANTLR-generated files with Python3 as target language, `antlr4 -Dlanguage=Python3 -listener oos.g4` .

To compile OOS code into C, `python3 main.py <name of OOS file>`

Then GCC to compile C code and run.


## Description of approach to assignment

This assignment was done using grammar actions to label recognized strings from an OOS input file, and when necessary, return them to other rules from the lower level ones, to the higher level ones, edited to reflect how this code should be written in C.

Then, at certain points, the Listener class gets to making the necessary checks not capable of being done at the grammar/Parser level, making sure issues don't come up, that the GCC compiler won't pick up, or that it won't give the necessary context to fix. It also prints out C code when necessary. That is, after the OOS code has been verified, at the statement level, or throughout the higher level rule functions, while descending.

# Specific notes on code

Put here not to bog down comments, read if further context is needed on some aspect of code.
The logic of grammar will not be described, since, other than factor and declarations, most rules have been changed only for label assignment.

## General conventions for C code

- Function overloading is handled by adding `$<function number with same name>` to the end of original function name.
- Constructors are named as such: `<name of class>constructor$<number of constructor>`.
- Inherited functions are denoted in C code by adding `$inh` after function name found in parent class. These can also be overloaded, as described above.
- Since no functions are allowed to be declared outside of a class, they all have been made to require being called as `self.function()` or `ID.function()`. The way this is handled in C is through adding to any given function arguments, the address of a struct instance, whose contents will be reached if referring to `self.`.

## class classContent

Added to myoosListener to be able to hold information on each class in object form.

Has fields:
- **name**, the name of a class.
- **fields**, the fields declared in class defition, which will be available to reach when having created a class instance. Organized as list of sublists, each structred as such: `[<type of following lists>, <field name>, <field name>, ...]`
- **parameters**, all sets of parameters of constructors declared. List of sublists, each containing a set of types that a constructor requires, each type being a string representation. Indexed by appearance of constructor in OOS code (index reflected in C code).
- **functions**, **funcParam** and **funcTypes**, three similarly indexed lists, to keep **function names** found in class as strings, **function parameters** *(structured similarly to parameters above, but one set of parameters per function name)*, and **function types** as strings, respectively. Function names are saved the way they'll be printed in C code.
- **inheritClasses**, a list of classContent objects, to represent inherited classes. 

## class CCodeTranslator

The class that inherits oosListener, and overrides some of its functions.

Has fields:
- **generated code**, an array to keep code to print out, in C form.
- **indent**, a counter to know how many indentations are required at any given point.
- **classes**, a list of classContent objects to represent found classes.
- **symTable**, a table of fields to be able to access when entering function or constructor. While it's named after a symbol table, it only keeps fields to able to access at a given time. Organized as list of sublists, each organized the way the fields list's sublists are in classContent.
- **replaceFunctions**, a list of sublists, each containing a couple of strings, the first to be replaced by the second, before adding to generated code. Used to replace function names found in OOS code with function names used in C code.

Now, on to its functions, some added as helper functions, and others to override oosListener functions.

First, the helper functions:

- `add_inherited_fields(inherited_classes, declared_fields)` helper function to recursively find and add inherited fields of a class, during its defition.

- `extend_fields(a,b)` merges symTable-like lists a and b.

- `helper_function_change(replacements, target_string)` replaces function names to ones used in C in a given string, using a list replacements (which is always field of class replaceFunctions).

- `function_helper(ctx)` does the job needed in both enterFactor() and enterDirect_call_stat(), which is to find the appropriate function to call, given the information available in both grammar rules, after checking if function call in OOS input file can be resolved, given the information acquired. Needs current rule context, which is given as argument.

- `error()` raises errors, returning an indicative message and error line.

Now, on to the functions that override those of oosListener.

- `enterClass_def()`, creates a struct to represent class in C generated code, and saves relevant data for later. Also declares all inherited functions, which will be written if not overriden by another inherited function. To handle being overriden by a function of this class, when resolving function calls, non-inherited functions are always given priority, not allowing inherited functions with same parameters to run.

- `enterClass_main_def()`, since class Main is not to be handled as a class, only find declarations, check for integrity, add them to list symTable, and generate code for them (outside of main function).

- `enterMethod_main_def()`, starts printing code for declaration of main function, finds declarations in main(), checks them, and adds code for them. Then merges locally found declarations with symTable (since, in C, fields of the same name inside of main function "override" those of global scope, and this Listener will only recognize those).

- `exitMethod_main_def()`, tidies up the code of main function (bracket, etc).

- `enterConstructor_def()`, checks for correct constructor definition, checks for parameters not having been used already, adds them to class object that was created during Class_def, and proceeds to check for duplicate fields between parameters and fields declared in constructor. Then adds code for those declarations, and proceeds to add code for the declaration of a pointer of a current class struct, named `$temp`. Its contents will reflect the changes the constructor makes to a class instance, before returning these contents. Finally fills up symTable with fields usable by constructor.

- `exitConstructor_def()`, empties symTable, and copies contents of `$temp` to a field of type of struct to return. Then returns that field.

- `enterMethod_def()`, processes function name, parameters, return type as given, and checks whether it would be fitting to be declared in C. That is, if actually overloading, change the function name as described in conventions to be able to declare in C. Then declaration follows in a similar fashion to constructor definition. Important to note that arguments follow the convention mentioned above, regarding `self`.

- `exitMethod_def()`, tidies up function definition.

- `enterMethod_body()`, handles declarations and adds them to symTable.

- `enterIf_stat()`, `enterElse_part()`, `enterWhile_part()` and `else` and `while` exit functions all function similarly, adding code for if/while blocks and conditions, making sure to edit indentation properly. Important to mention that an else block will be generated regardless of its existence in OOS code, but will be empty in that case.

- `exitStatement()` is where code generation for statements takes place. After distinguishing type of statement based on rule context, modify string returned from parser to fit the C code necessary. One of these modifications is changing the names of functions from those mentioned in OOS to their C equivalents. Constructor call assignments are particularly important, with them being handled almost the same way as that in helper function `function_helper(ctx)`.

