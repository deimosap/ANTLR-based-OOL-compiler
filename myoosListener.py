from antlr4 import *
import sys

## imports to be able to generate code from the listener
from oosLexer import oosLexer
from oosParser import oosParser
from oosListener import oosListener


class classContent():
	def __init__(self, name):
		## name of class
		self.name = name

		## fields of class
		self.fields = []

		## possible parameters for class
		self.parameters = []

		## holds function names
		self.functions = []

		## holds function parameters
		self.funcParam = []

		## holds function types
		self.funcTypes = []

		## holds inherited class objects
		self.inheritClasses = []


class CCodeTranslator(oosListener):

	def __init__(self):
		## array to function as stack of generated code
		self.generated_code = []
		## indentation counter
		self.indent = 0
		## found classes
		self.classes = []
		## table of possible fields to access when entering function
		self.symTable = []
		## holds OOS names of functions to be replaced by C names
		self.replaceFunctions = []
	

	def indent(self):
		return ("	"*(self.indent))
	

	def error(self, msg, cur_line):
		sys.exit(f"\n-- ERROR -- near line {cur_line}\n{msg}\n")


	def enterClasses(self, ctx:oosParser.ClassesContext):
		self.generated_code.append("#include <stdio.h>\n#include <stdlib.h>\n\n")


	## helper function, finds and adds inherited fields of class
	def add_inherited_fields(self, inherited_classes, declared_fields):
		for inhClass in inherited_classes:
	        ## recursively process fields of inherited classes' parents
			self.add_inherited_fields(inhClass.inheritClasses, declared_fields)

			## add fields of the current inherited class
			for typeList in inhClass.fields:
				field_type = typeList[0]
				for field in typeList[1:]:
					if (field_type, field) not in declared_fields:
						self.generated_code.append(self.indent * "    " + f"{field_type} {field};\n")
						declared_fields.add((field_type, field))
	
	## helper function to merge symTable created by methods
	def extend_fields(self, a, b):
		## create a dictionary to easily find existing types in list a
		a_dict = {sublist[0]: sublist[1:] for sublist in a}

		## iterate through list b
		for sublist in b:
			field_type = sublist[0]
			fields = sublist[1:]

			if field_type in a_dict:
				## if type already exists in a, extend the field names
				a_dict[field_type].extend(fields)
			else:
				## if type doesn't exist in a, add it to a_dict
				a_dict[field_type] = fields

		## convert the dictionary back to a list of lists format
		result = [[key] + value for key, value in a_dict.items()]
		return result

	## replaces function names to ones used in C
	def helper_function_change(self, replacements, target_string):
		current_index = 0
		for old, new in replacements:
			## find the first instance of the substring to replace after the current index
			index = target_string.find(old, current_index)
			if index != -1:
				## perform the replacement at the first instance
				target_string = target_string[:index] + new + target_string[index + len(old):]
				## update the index to move past the replaced part
				current_index = index + len(new)
		return target_string


	def enterClass_def(self, ctx:oosParser.Class_defContext):
		## check if class with this name has already been defined
		if next((c for c in self.classes if c.name == ctx.cl_n1.getText()), None):
			self.error(f"Class {ctx.cl_n1.getText()} defined twice.", ctx.start.line)

		## code for struct name
		## typedef used to refer to fields in a similar fashion to OOS
		self.generated_code.append(f"typedef struct {ctx.cl_n1.getText()}" + "{\n")
		self.indent += 1

		## create classContent object
		curClass = classContent(ctx.cl_n1.getText())

		## get info on inherited classes
		for inClass in ctx.inherited:
			## find class to add necessary fields and methods
			## this will also allow us to trigger an error if class name has not been found			
			inherited_class = next((c for c in self.classes if c.name == inClass), None)
			
			## adding class to inherited classes here
			if inherited_class:
				curClass.inheritClasses.append(inherited_class)
			else:
				self.error(f"Class {inClass} inherited by {curClass.name} not found.", ctx.start.line)

		## find declarations and add necessary fields
		## decl.decl is used to get the list of declarations, otherwise context
		for decl_line in ctx.decl.decl:

			## parse first string, type
            ## parse the rest as list of fields
			field_type = decl_line[0]
			field_names = decl_line[1:]			

            ## check if this type is already in the current class fields
			existing_field = next((f for f in curClass.fields if f[0] == field_type), None)
           
			if existing_field:
				## check for duplicate fields in the current class
				for field in field_names:
					if field in existing_field[1:]:
						self.error(f"Field {field} of type {field_type} declared multiple times in class {curClass.name}.", ctx.start.line)
					## all ok, add field to existing type
					existing_field.append(field)
			else:
				## add new type with fields
				curClass.fields.append([field_type] + field_names)

		## declare all fields in each list
		## set to keep declared fields, no duplicates between inherited and current classes
		declared_fields = set()

		## add current class' fields indiscriminately
		for typeList in curClass.fields:
			field_type = typeList[0]
			for field in typeList[1:]:
				self.generated_code.append(self.indent*"    " + f"{field_type} {field};\n")
				declared_fields.add((field_type, field))

		## add generated code for inherited fields, checking if declared
		self.add_inherited_fields(curClass.inheritClasses, declared_fields)

		## close the struct definition and add typedef for the class
		self.indent -= 1
		self.generated_code.append("}"+f" {curClass.name};\n\n")

		## add the current class to the list of known classes
		self.classes.append(curClass)
		
		## iterate through every inherited class of current one
		for inhClass in self.classes[-1].inheritClasses:
			## iterate through every function of theirs
			for inhIndex, inhFunctionName in enumerate(inhClass.functions):
				inheritCheck = True
				nameCounter = 0
				## iterate through all functions of current class to find if they override all of them
				for curIndex, curFunctionName in enumerate(self.classes[-1].functions):
					if inhFunctionName.split('$')[0] == curFunctionName.split('$')[0]:
						nameCounter += 1

					## check overlap between type, function OOS name  and parameters
					if inhClass.funcTypes[inhIndex] == self.classes[-1].funcTypes[curIndex] and inhClass.funcParam[inhIndex] == self.classes[-1].funcParam[curIndex] and inhFunctionName.split('$')[0] == curFunctionName.split('$')[0]:
						## overriden, don't bring inherited function in
						inheritCheck = False
				
				## iterated through all current functions, add if not overriden, add
				if inheritCheck:
					addFuncName = inhFunctionName.split('$')[0] + f"$inh${self.classes[-1].name}"
					if nameCounter:
						addFuncName += f"${nameCounter}"

					addFuncType = inhClass.funcTypes[inhIndex]

					## add to current class lists to call later
					self.classes[-1].functions.append(addFuncName)
					self.classes[-1].funcTypes.append(addFuncType)
					self.classes[-1].funcParam.append(inhClass.funcParam[inhIndex])

					## function parameters in string form
					addFuncParam = ""
					## function parameters to call inherited function
					callFuncParam = ""

					argCounter = 1
					## make arguments to be called as (<type1> arg1, <type2> arg2)
					for element in inhClass.funcParam[inhIndex]:
						addFuncParam += f"{element} arg{argCounter}, "
						callFuncParam += f"arg{argCounter}, "
						argCounter += 1

					## declare new function
					self.generated_code.append(f"{addFuncType} {addFuncName}({addFuncParam}{self.classes[-1].name} *$temp)" + '{\n')
					self.indent += 1
					## create new instance of inherited class' struct
					self.generated_code.append(self.indent*"	" + f"{inhClass.name} inherited;\n")
					## fill it up with fields that have been inherited
					for typeList in inhClass.fields:
						for element in typeList[1:]:
							self.generated_code.append(self.indent*"	" + f"inherited.{element} = $temp->{element};\n")

					## don't return if void
					if addFuncType != "void":
						self.generated_code.append(self.indent*"	" + f"{addFuncType} $returnval = ")
					else:
						self.generated_code.append(self.indent*"	")
					
					## call function
					self.generated_code.append(f"{inhFunctionName}({callFuncParam}&inherited);\n")

					## fill child class up again with possibly changed fields
					for typeList in inhClass.fields:
						for element in typeList[1:]:
							self.generated_code.append(self.indent*"	" + f"$temp->{element} = inherited.{element};\n")

					## don't return if void
					if addFuncType != "void":
						self.generated_code.append(self.indent*"	" + f"return $returnval;\n")

					## tidy up function declaration
					self.generated_code.append("}\n")
					self.indent -= 1
	

	def enterClass_main_def(self, ctx:oosParser.Class_main_defContext):
		## find declarations and add necessary fields
		for decl_line in ctx.decl.decl:
			## parse first string, type
            ## parse the rest as list of fields
			field_type = decl_line[0]
			field_names = decl_line[1:]		

            ## check if this type is already in fields
			existing_field = next((f for f in self.symTable if f[0] == field_type), None)
        
			if existing_field:
				## check for duplicate fields
				for field in field_names:
					if field in existing_field[1:]:
						self.error(f"Field {field} of type {field_type} declared multiple times in program.", ctx.start.line)
					## all ok, add field to existing type
					existing_field.append(field)
			else:
				## add new type with fields
				self.symTable.append([field_type] + field_names)

		## add fields indiscriminately
		for typeList in self.symTable:
			field_type = typeList[0]
			for field in typeList[1:]:
				self.generated_code.append(f"{field_type} {field};\n")
	
	
	def enterMethod_main_def(self, ctx:oosParser.Method_main_defContext):
		## start printing code for main
		self.generated_code.append("int main(){\n")
		self.indent += 1

		## for declarations found here, to be printed here
		notSymTable = []

		## find declarations, add to symTable and print in program
		for decl_line in ctx.decl.decl:

			## parse first string, type
            ## parse the rest as list of fields
			field_type = decl_line[0]
			field_names = decl_line[1:]			

            ## check if this type is already in fields
			existing_field = next((f for f in notSymTable if f[0] == field_type), None)
           
			if existing_field:
				## check for duplicate fields in the current class
				for field in field_names:
					if field in existing_field[1:]:
						self.error(f"Field {field} of type {field_type} declared multiple times in main.", ctx.start.line)
					## all ok, add field to existing type, if existing already, GCC will see local field before global
					existing_field.append(field)
			else:
				## add new type with fields
				notSymTable.append([field_type] + field_names)
		
		## add fields indiscriminately
		for typeList in notSymTable:
			field_type = typeList[0]
			for field in typeList[1:]:
				self.generated_code.append(self.indent*"	" + f"{field_type} {field};\n")

		## merge with symTable
		self.symTable = self.extend_fields(self.symTable, notSymTable)
	

	## overriding method exitMethod_main_def
	def exitMethod_main_def(self, ctx:oosParser.Method_main_defContext):
		## just tidy up main
		self.symTable = []
		self.generated_code.append("}")
		self.indent -= 1


	def enterConstructor_def(self, ctx:oosParser.Constructor_defContext):
		## check for cl being the type of the latest class in stack classes
		## error otherwise
		curClass_name = self.classes[-1].name
		if not curClass_name == ctx.cl.getText():
			self.error(f"Constructor of class {curClass_name} should not return type {ctx.cl.getText()}.", ctx.start.line)

		## find parameters and add to parameters of latest class in stack (if already there, error)
		## get to isolate the odd-indexed elements of list (since it is organized as [<type>, <name>, <type>, ...])
		paramTypes = ctx.plist.plist[::2]
		if paramTypes in self.classes[-1].parameters:
			self.error(f"Constructor of class {curClass_name} with parameters {paramTypes} has been declared more than once.", ctx.start.line)
		self.classes[-1].parameters.append(paramTypes)
		
		## find size of self.classes[-1].parameters
		## it will be equal to number of constructors needed as of now
		conNum = len(self.classes[-1].parameters)

		## to print the constructor method later
		## iterate through plist and produce a fitting string param
		param = ""
		## make a declarations-like list of parameters
		## temp because it will be in a state similar to the list declarations returns
		paramtemp = []

		for index, item in enumerate(ctx.plist.plist):
			if index % 2 == 0:
				## here, end of string will be "...<type> <field>"
				if index != 0:
					param += ", "
				## add field type to end of string
				param += item
				## add field type as type list
				paramtemp.append([item])
			else:
				## add field name to end of string
				param += " "+item
				## add field name as second element of type list
				paramtemp[-1].append(item)

		## paramCheck will be a proper declarations-like list of parameters
		paramCheck = []

		## create paramCheck and look for duplicate parameters (approach mirrored in declarations)
		for parameter in paramtemp:
			field_type = parameter[0]
			field_name = parameter[1]

			existing_field = next((p for p in paramCheck if p[0] == field_type), None)

			if existing_field:
				## check for duplicate fields
				if field_name in existing_field[1:]:
					self.error(f"Multiple parameters {field_name} of type {field_type} in constructor number {conNum} of class {curClass_name}.", ctx.start.line)
				## all ok, add parameter to existing type
				existing_field.append(field_name)
			else:
				## add new type with parameter
				paramCheck.append([field_type, field_name])

		## print declarations and have to keep in some list here, too
		## just check for repeated declarations
		conFields = []

		for decl_line in ctx.decl.decl:
			## parse first string, type
            ## parse the rest as list of fields
			field_type = decl_line[0]
			field_names = decl_line[1:]			

            ## check if this type is already in the current class fields
			existing_field = next((f for f in conFields if f[0] == field_type), None)
           
			if existing_field:
				## check for duplicate fields
				for field in field_names:
					if field in existing_field[1:]:
						self.error(f"Field {field} of type {field_type} declared multiple times in constructor of class {curClass_name}.",ctx.start.line)
					## all ok, add field to existing type
					existing_field.append(field)
			else:
				## add new type with fields
				conFields.append([field_type] + field_names)
			
			## check that none of the fields found in declarations are in parameters
			existing_param = next((p for p in paramCheck if p[0] == field_type), None)
			if existing_param:
				for field in field_names:
					if field in existing_param[1:]:
						self.error(f"Field {field} of type {field_type} conflicts with parameter of same name in constructor number {conNum} of class {curClass_name}.", ctx.start.line)
		
		## create the function, with added argument, a pointer to a struct of Class type
		## first, check if there are any parameters
		parametersString = ""
		if len(paramTypes)> 0:
			parametersString += param
		
		## create the constructor method
		self.generated_code.append(f"{curClass_name} {curClass_name}$constructor{conNum}({parametersString})"+"{\n")
		self.indent += 1

		## print declarations within method
		for typeList in conFields:
			field_type = typeList[0]
			for field in typeList[1:]:
				self.generated_code.append(self.indent*"	" + f"{field_type} {field};\n")

		## create a pointer to struct of type <class type>
		self.generated_code.append(self.indent*"	" + f"{curClass_name} *$temp;\n")
		## allocate memory for struct
		self.generated_code.append(self.indent*"	" + f"$temp = ({curClass_name} *) malloc(sizeof({curClass_name}));\n")

		## add to symTable, the fields usable by constructor before heading to body
		self.symTable = self.extend_fields(paramCheck, conFields)


	def exitConstructor_def(self, ctx:oosParser.Constructor_defContext):
		## empty up symbol table since everything is done now
		self.symTable = []
		## tidy up the constructor function, after method body
		self.generated_code.append(self.indent*"	" + f"{self.classes[-1].name} $retvalue = *$temp;\n")
		self.generated_code.append(self.indent*"	" + "free($temp);\n")
		self.generated_code.append(self.indent*"	" + "return $retvalue;\n")
		self.generated_code.append("}\n")
		self.indent -= 1


	def enterMethod_def(self, ctx:oosParser.Method_defContext):
		## get current class name to know the type of pointer to put in arguments
		curClass_name = self.classes[-1].name

		## find parameters and add to function parameters in latest class
		## if same name and parameters as another, throw error
		## get to isolate the odd-indexed elements of list (since it is organized as [<type>, <name>, <type>, ...])
		paramTypes = ctx.plist.plist[::2]

		## get return type of function
		retType = ""
		if ctx.typeint:
			retType += "int"
		elif ctx.voidtype:
			retType += "void"
		else:
			retType += ctx.cl_n.cl_n

		## traverse through sets of function parameters (and function names since they share indices)
		for index,item in enumerate(self.classes[-1].funcParam):
			## compare to actual name, without number of function, or return type
			inherited = False
			if len(self.classes[-1].functions[index].split('$'))>1:
				inherited = self.classes[-1].functions[index].split('$')[1] == "inh"
			
			if ctx.funcname.text ==  self.classes[-1].functions[index].split('$')[0] and not inherited:
				## if parameters are the same, and so is return type, not overloading 
				if paramTypes == item and retType == self.classes[-1].funcTypes[index]:
					self.error(f"Function {ctx.funcname.text} of class {curClass_name} with parameters {paramTypes} and return type {retType} has been declared more than once.", ctx.start.line)

		## keep function name
		functionName = ctx.funcname.text

		## counter to keep how many functions of same name found in general
		sameName = 0
		for classObj in self.classes:
			for foundFunction in classObj.functions:
				if foundFunction.split('$')[0] == functionName:
					sameName += 1

		## more than one found with same name, but overloading rules allow for this
		if sameName:
			functionName += f"${sameName}"
			
		## add function to class fields
		self.classes[-1].functions.append(functionName)
		self.classes[-1].funcParam.append(paramTypes)
		self.classes[-1].funcTypes.append(retType)

		## to print the constructor method later
		## iterate through plist and produce a fitting string param
		param = ""
		## make a declarations-like list of parameters
		## temp because it will be in a state similar to the list declarations returns
		paramtemp = []

		for index, item in enumerate(ctx.plist.plist):
			if index % 2 == 0:
				## here, end of string will be "...<type> <field>"
				if index != 0:
					param += ", "
				## add field type to end of string
				param += item
				## add field type as type list
				paramtemp.append([item])
			else:
				## add field name to end of string
				param += " "+item
				## add field name as second element of type list
				paramtemp[-1].append(item)

		## paramCheck will be a proper declarations-like list of parameters
		paramCheck = []

		## create paramCheck and look for duplicate parameters (approach mirrored in declarations)
		for parameter in paramtemp:
			field_type = parameter[0]
			field_name = parameter[1]

			existing_field = next((p for p in paramCheck if p[0] == field_type), None)

			if existing_field:
				## check for duplicate fields
				if field_name in existing_field[1:]:
					self.error(f"Multiple parameters {field_name} of type {field_type} in function {functionName} of class {curClass_name}.", ctx.start.line)
				## all ok, add parameter to existing type
				existing_field.append(field_name)
			else:
				## add new type with parameter
				paramCheck.append([field_type, field_name])

		## print declarations and have to keep in some list here, too
		## just check for repeated declarations (approach mirrored above)
		## these, unless returned, remain in constructor
		methodFields = []

		for decl_line in ctx.decl.decl:
			## parse first string, type
            ## parse the rest as list of fields
			field_type = decl_line[0]
			field_names = decl_line[1:]			

            ## check if this type is already in the current class fields
			existing_field = next((f for f in methodFields if f[0] == field_type), None)
           
			if existing_field:
				## check for duplicate fields
				for field in field_names:
					if field in existing_field[1:]:
						self.error(f"Field {field} of type {field_type} declared multiple times in constructor of class {curClass_name}.", ctx.start.line)
					## all ok, add field to existing type
					existing_field.append(field)
			else:
				## add new type with fields
				methodFields.append([field_type] + field_names)
			
			## check that none of the fields found in declarations are in parameters
			existing_param = next((p for p in paramCheck if p[0] == field_type), None)
			if existing_param:
				for field in field_names:
					if field in existing_param[1:]:
						self.error(f"Field {field} of type {field_type} conflicts with parameter of same name in function {functionName} of class {curClass_name}.", ctx.start.line)
		
		## create the function, with added argument, a pointer to a struct of Class type
		## first, check if there are any parameters
		parametersString = ""
		if len(paramTypes)> 0:
			parametersString += param + ','
		self.generated_code.append(f"{retType} {functionName}({parametersString} {curClass_name} *$temp)"+"{\n")
		self.indent += 1

		## print declarations within method
		for typeList in methodFields:
			field_type = typeList[0]
			for field in typeList[1:]:
				self.generated_code.append(self.indent*"	" + f"{field_type} {field};\n")

		## add to symTable, the fields usable by constructor before heading to body
		## symTable will be a declaration-like list
		self.symTable = self.extend_fields(paramCheck, methodFields)


	def exitMethod_def(self, ctx:oosParser.Constructor_defContext):
		## empty up symbol table since everything is done now
		self.symTable = []
		## tidy up the function, after method body
		self.generated_code.append("}\n")
		self.indent -= 1


	def enterMethod_body(self, ctx:oosParser.Method_bodyContext):
		## get declarations from this context
		for decl_line in ctx.decl.decl:
			## parse first string, type
            ## parse the rest as list of fields
			field_type = decl_line[0]
			field_names = decl_line[1:]			

            ## check if this type is in parameters or declarations previously
			existing_field = next((f for f in self.symTable if f[0] == field_type), None)
           
			if existing_field:
				## check for duplicate fields
				for field in field_names:
					if field in existing_field[1:]:
						self.error(f"Field {field} of type {field_type} declared multiple times in constructor of class {self.classes[-1].name}.", ctx.start.line)
					existing_field.append(field)		
			else:
				## add new type with fields
				self.symTable.append([field_type] + field_names)

	## similar to while
	## other than the fact that bracket closing and whatnot gets handled in else_part
	def enterIf_stat(self, ctx:oosParser.If_statContext):
		self.generated_code.append(self.indent*"	" + "if (" + ctx.cond.cond + ")" + "{\n")
		self.indent += 1


	## closing if block's bracket
	## creating else block
	def enterElse_part(self, ctx:oosParser.Else_partContext):
		self.indent -= 1
		self.generated_code.append(self.indent*"	" + "}\n")
		self.generated_code.append(self.indent*"	" + "else {\n")
		self.indent += 1


	## tidying up
	def exitElse_part(self, ctx:oosParser.Else_partContext):
		self.indent -= 1
		self.generated_code.append(self.indent*"	" + "}\n")
	

	## print code for the while statement, without sub-statements
	## also take care of indentation moving on
	def enterWhile_stat(self, ctx:oosParser.While_statContext):
		self.generated_code.append(self.indent*"	" + "while (" + ctx.cond.cond + ")" + "{\n")
		self.indent += 1


	## just take care of bottom bracket and indentation
	def exitWhile_stat(self, ctx:oosParser.While_statContext):
		self.indent -= 1
		self.generated_code.append(self.indent*"	" + "}\n")


	## code will have to be generated in statements
	def exitStatement(self, ctx:oosParser.StatementContext):
		if ctx.ret:
			code = ctx.ret.s
			code.replace("\n", "\n"+self.indent*"	")
			code += "\n"

			code = self.helper_function_change(self.replaceFunctions, code)
			self.replaceFunctions = []

			self.generated_code.append(self.indent*"	" + code)
			
		elif ctx.inputs:
			code = ctx.inputs.s
			code.replace("\n", "\n"+self.indent*"	")
			code += "\n"
			self.generated_code.append(self.indent*"	" + code)
		
		elif ctx.prints:
			code = ctx.prints.s
			code = code.replace("\n", "\n"+self.indent*"	")
			code += 'printf("\\n"); \n'

			code = self.helper_function_change(self.replaceFunctions, code)
			self.replaceFunctions = []

			self.generated_code.append(self.indent*"	" + code)
		
		elif (ctx.assign and ctx.assign.exp):
			code = ctx.assign.s
			code.replace("\n", "\n"+self.indent*"	")
			code += "\n"

			code = self.helper_function_change(self.replaceFunctions, code)
			self.replaceFunctions = []

			self.generated_code.append(self.indent*"	" + code)
		
		## constructor call assigned to field, so check needed
		elif ctx.assign and ctx.assign.cc:
			## get constructor class name
			cl_n = ctx.assign.cc.cc[0]
			## get constructor arguments
			args = ctx.assign.cc.cc[1:]
			## c is the desired class
			c = next((c for c in self.classes if c.name == cl_n), None)

			## find set of parameters here
			## hence index, hence call correct constructor
			if c:
				## go to symTable and find possible types for all arguments to compare with each function
				argPossibleTypes = []
				for arg in args:
					## sublist for possible types of this argument
					argPossibleSublist = []
					## access every possible type in symTable
					## where we'll search for either:
					# - a field
					# - a subfield of field
					# - a function of field
					for typeList in self.symTable:
						typeName = typeList[0]
						fieldNames = typeList[1:]
					
						## if subfield, must contain '.'
						isASubfield = len(arg.split('.'))>1
						## if function, must contain an address to struct instance as last parameter
						isAFunction = len(arg.split('&'))>1
					
						if isAFunction:	
							## parse function name by getting the last function called in argument
							argFunction = arg.split('&')[0].split('(')[0]
							funcField = arg.split('&')[-1].split(')')[0]

							## get possible classes for funcField
							funcPossibleClasses = []
							for subTypeList in self.symTable:
								subTypeName = subTypeList[0]
								subTypeNames = subTypeList[1:]

								if funcField in subTypeNames:
									funcPossibleClasses.append(subTypeName)
						
							for funcPossibleClass in funcPossibleClasses:
								## class object for funcPossibleClass
								c = next((c for c in self.classes if c.name == funcPossibleClass), None)
								for idx, possibleFunc in enumerate(c.functions):
									if possibleFunc.split('$')[0] == argFunction:
										argPossibleSublist.append(c.funcTypes[idx])

						## resolve type of subfield
						elif isASubfield:
							if arg.split('.')[0] in fieldNames:
								## go to fields of type typeName
								## c is the desired class
								c = next((c for c in self.classes if c.name == typeName), None)

								## find fitting field
								if c:
									for subTypeList in c.fields:
										subTypeName = subTypeList[0]
										subTypeNames = subTypeList[1:]

										if arg.split('.')[-1] in subTypeNames:
											argPossibleSublist.append(subTypeName)

						## other cases not valid, go for field
						elif arg in fieldNames:
							argPossibleSublist.append(typeName)

				
					## check for objects of self
					isSelf = len(arg.split('$'))>1
					if isSelf:
						isFunction = len(arg.split('&'))>1
						isField = len(arg.split('>'))>1
					
						## access fields of self to find one fitting
						## $temp->field will be found
						if isField:
							for fieldList in self.classes[-1].fields:
								curFieldType = fieldList[0]
								curFields = fieldList[1:]

								if arg.split('>')[1] in curFields:
									argPossibleSublist.append(curFieldType)
					

						## access functions of self to find one fitting
						elif isFunction:
							## parse function name by getting the last function called in argument
							argFunction = arg.split('&')[0].split('(')[0]

							for idx, possibleFunc in enumerate(self.classes[-1].functions):
								if possibleFunc.split('$')[0] == argFunction:
									argPossibleSublist.append(self.classes[-1].funcTypes[idx])

					## if arg is a number, append "int"
					if arg.isnumeric():
						argPossibleSublist.append("int")
				
					argPossibleTypes.append(argPossibleSublist)

				## keep the parameter set that fits here -- if staying 0, error
				conNum = 0
				
				## now need to find a possible combination of types to work with a sublist of parameters
				## iterate through parameter sets in c and find a fit
				for paramSetIndex, paramSet in enumerate(c.parameters):
					## check for incompatible length
					if len(paramSet) != len(args):
						continue
					## keep if parameter set fits
					isMatch = True
					## iterate through every parameter in a set and check if it fits
					for paramIndex, paramType in enumerate(paramSet):						
						if paramType not in argPossibleTypes[paramIndex]:
							isMatch = False
							break
					## found no problems, give this set of parameters
					if isMatch:
						conNum = paramSetIndex + 1
						break
	
				if conNum == 0:
					self.error(f"No constructor found that suits set of parameters {args} .", ctx.start.line)
				
				## put arguments in fitting string
				arguments = ", ".join(args)

				## add code now, with s string being '<field> ='
				self.generated_code.append( self.indent*"	" +ctx.assign.s + f"{c.name}$constructor{conNum}({arguments});\n" )

			else:
				self.error(f"Constructor call for class {cl_n} not found, since class has not been defined.", ctx.start.line)

		## need to print for direct call stat, checks done at exit of direct call
		elif ctx.direct:
			## similar to how factors are handled, merge all except for option index (used at checks)
			s = ''.join(ctx.direct.f[1:])
			s = self.helper_function_change(self.replaceFunctions, s)
			
			self.replaceFunctions = []

			## add code now
			self.generated_code.append( self.indent*"	" + s + ";\n" )


	## helper function to check for and find function names, to use with both factor and direct_call_stat
	def function_helper(self,ctx):
		## function call from field
		if ctx.f[0] == '4':
			## field identifier
			fieldName = ctx.idd.text
			## field possible types kept here, it will be last argument of function
			fieldPossibleTypes = []

			## field from current class, so use self, can't be main
			if ctx.self:
				curClass = self.classes[-1]

				for fieldType in curClass.fields:
					if fieldName in fieldType[1:]:
						fieldPossibleTypes.append(fieldType[0])
				
				if len(fieldPossibleTypes) == 0:
					self.error(f"No such field with name {fieldName} in class {curClass.name}.", ctx.start.line)
			
			## field from some field ID
			else:
				fieldName = ctx.idd.text

				for fieldType in self.symTable:
					if fieldName in fieldType[1:]:
						fieldPossibleTypes.append(fieldType[0])
				
				if len(fieldPossibleTypes) == 0:
					self.error(f"No such field with name {fieldName} in current scope.", ctx.start.line)
				
			## go to symTable and find possible types for all arguments to compare with each function
			argPossibleTypes = []
			for arg in ctx.func.fcall[1]:
				## sublist for possible types of this argument
				argPossibleSublist = []
				## access every possible type in symTable
				## where we'll search for either:
				# - a field
				# - a subfield of field
				# - a function of field
				for typeList in self.symTable:
					typeName = typeList[0]
					fieldNames = typeList[1:]
					
					## if subfield, must contain '.'
					isASubfield = len(arg.split('.'))>1
					## if function, must contain an address to struct instance as last parameter
					isAFunction = len(arg.split('&'))>1
					
					if isAFunction:	
						## parse function name by getting the last function called in argument
						argFunction = arg.split('&')[0].split('(')[0]
						funcField = arg.split('&')[-1].split(')')[0]

						## get possible classes for funcField
						funcPossibleClasses = []
						for subTypeList in self.symTable:
							subTypeName = subTypeList[0]
							subTypeNames = subTypeList[1:]

							if funcField in subTypeNames:
								funcPossibleClasses.append(subTypeName)
						
						for funcPossibleClass in funcPossibleClasses:
							## class object for funcPossibleClass
							c = next((c for c in self.classes if c.name == funcPossibleClass), None)
							for idx, possibleFunc in enumerate(c.functions):
								if possibleFunc.split('$')[0] == argFunction:
									argPossibleSublist.append(c.funcTypes[idx])

					## resolve type of subfield
					elif isASubfield:
						if arg.split('.')[0] in fieldNames:
							## go to fields of type typeName
							## c is the desired class
							c = next((c for c in self.classes if c.name == typeName), None)

							## find fitting field
							if c:
								for subTypeList in c.fields:
									subTypeName = subTypeList[0]
									subTypeNames = subTypeList[1:]

									if arg.split('.')[-1] in subTypeNames:
										argPossibleSublist.append(subTypeName)

					## other cases not valid, go for field
					elif arg in fieldNames:
						argPossibleSublist.append(typeName)

				
				## check for objects of self
				isSelf = len(arg.split('$'))>1
				if isSelf:
					isFunction = len(arg.split('&'))>1
					isField = len(arg.split('>'))>1
					
					## access fields of self to find one fitting
					## $temp->field will be found
					if isField:
						for fieldList in self.classes[-1].fields:
							curFieldType = fieldList[0]
							curFields = fieldList[1:]

							if arg.split('>')[1] in curFields:
								argPossibleSublist.append(curFieldType)
					

					## access functions of self to find one fitting
					elif isFunction:
						## parse function name by getting the last function called in argument
						argFunction = arg.split('&')[0].split('(')[0]

						for idx, possibleFunc in enumerate(self.classes[-1].functions):
							if possibleFunc.split('$')[0] == argFunction:
								argPossibleSublist.append(self.classes[-1].funcTypes[idx])

				## if arg is a number, append "int"
				if arg.isnumeric():
					argPossibleSublist.append("int")
				
				argPossibleTypes.append(argPossibleSublist)
			
			## now we know some of the possible classes in which to find
			## search these classes for a function where name and arguments agree
			## keep found function name here, no inherited functions yet
			functionName = ""
			for possibleClass in self.classes:
				## field can't be one such type
				if possibleClass.name not in fieldPossibleTypes:
					continue
					
				for funcIndex, funcName in enumerate(possibleClass.functions):
					inherited = False
					if len(funcName.split('$'))>1:
						inherited = funcName.split('$')[1] == "inh"
					if not ctx.func.fcall[0][0] == funcName.split('$')[0] or inherited:
						continue
					## check for parameters being correct
					if not len(argPossibleTypes) == len(possibleClass.funcParam[funcIndex]):
						continue
					isMatch = True
					for parameterIndex, parameterType in enumerate(possibleClass.funcParam[funcIndex]):
						if not parameterType in argPossibleTypes[parameterIndex]:
							isMatch = False
							break
						
					if isMatch:
						functionName += funcName
						break
			
			## now go for inherited functions only
			if functionName == "":
				for possibleClass in self.classes:
					## field can't be one such type
					if possibleClass.name not in fieldPossibleTypes:
						continue
					
					for funcIndex, funcName in enumerate(possibleClass.functions):
						if len(funcName.split('$'))>1:
							inherited = funcName.split('$')[1] == "inh"
						
						if not ctx.func.fcall[0][0] == funcName.split('$')[0] or not inherited:
							continue
						## check for parameters being correct
						if not len(argPossibleTypes) == len(possibleClass.funcParam[funcIndex]):
							continue
						isMatch = True
						for parameterIndex, parameterType in enumerate(possibleClass.funcParam[funcIndex]):
							if not parameterType in argPossibleTypes[parameterIndex]:
								isMatch = False
								break
						
						if isMatch:
							functionName += funcName
							break

			## if still empty
			if functionName == "":
				self.error(f"No function {ctx.func.fcall[0][0]} found in class instance {fieldName}.", ctx.start.line)
				
			self.replaceFunctions.append([ctx.f[1], functionName])

		## function call from self
		elif ctx.f[0] == '5':
			
			## go to symTable and find possible types for all arguments to compare with each function
			argPossibleTypes = []
			for arg in ctx.func.fcall[1]:
				## sublist for possible types of this argument
				argPossibleSublist = []
				## access every possible type in symTable
				## where we'll search for either:
				# - a field
				# - a subfield of field
				# - a function of field
				for typeList in self.symTable:
					typeName = typeList[0]
					fieldNames = typeList[1:]
					
					## if subfield, must contain '.'
					isASubfield = len(arg.split('.'))>1
					## if function, must contain an address to struct instance as last parameter
					isAFunction = len(arg.split('&'))>1
					
					if isAFunction:
						
						## parse function name by getting the last function called in argument
						argFunction = arg.split('&')[0].split('(')[0]
						funcField = arg.split('&')[-1].split(')')[0]

						## get possible classes for funcField
						funcPossibleClasses = []
						for subTypeList in self.symTable:
							subTypeName = subTypeList[0]
							subTypeNames = subTypeList[1:]

							if funcField in subTypeNames:
								funcPossibleClasses.append(subTypeName)
						
						for funcPossibleClass in funcPossibleClasses:
							## class object for funcPossibleClass
							c = next((c for c in self.classes if c.name == funcPossibleClass), None)
							for idx, possibleFunc in enumerate(c.functions):
								if possibleFunc.split('$')[0] == argFunction:
									argPossibleSublist.append(c.funcTypes[idx])

					elif isASubfield:
						if arg.split('.')[0] in fieldNames:
							## go to fields of type typeName
							## c is the desired class
							c = next((c for c in self.classes if c.name == typeName), None)

							## find fitting field
							if c:
								for subTypeList in c.fields:
									subTypeName = subTypeList[0]
									subTypeNames = subTypeList[1:]

									if arg.split('.')[-1] in subTypeNames:
										argPossibleSublist.append(subTypeName)

					## other cases not valid, go for field
					elif arg in fieldNames:
						argPossibleSublist.append(typeName)

				
				## check for objects of self
				isSelf = len(arg.split('$'))>1
				if isSelf:
					isFunction = len(arg.split('&'))>1
					isField = len(arg.split('>'))>1
					
					## access fields of self to find one fitting
					if isField:
						for fieldList in self.classes[-1].fields:
							curFieldType = fieldList[0]
							curFields = fieldList[1:]

							if arg.split('>')[1] in curFields:
								argPossibleSublist.append(curFieldType)
					

					## access functions of self to find one fitting
					elif isFunction:
						## parse function name by getting the last function called in argument
						argFunction = arg.split('&')[0].split('(')[0]

						for idx, possibleFunc in enumerate(self.classes[-1].functions):
							if possibleFunc.split('$')[0] == argFunction:
								argPossibleSublist.append(self.classes[-1].funcTypes[idx])

				## if arg is a number, append "int"
				if arg.isnumeric():
					argPossibleSublist.append("int")
				
				argPossibleTypes.append(argPossibleSublist)

			## keep found function name here, again, only non-inherited here
			functionName = ""	
			for funcIndex, funcName in enumerate(self.classes[-1].functions):
				inherited = False
				if len(funcName.split('$'))>1:
						inherited = funcName.split('$')[1] == "inh"
				if (not ctx.func.fcall[0][0] == funcName.split('$')[0]) or inherited:
					continue
				## check for parameters being correct
				if not len(argPossibleTypes) == len(self.classes[-1].funcParam[funcIndex]):
					continue
				isMatch = True
				for parameterIndex, parameterType in enumerate(self.classes[-1].funcParam[funcIndex]):
					if not parameterType in argPossibleTypes[parameterIndex]:
						isMatch = False
						break
						
				if isMatch:
					functionName += funcName
					break
			
			## now check only inherited
			if functionName == "":
				for funcIndex, funcName in enumerate(self.classes[-1].functions):
					if not ctx.func.fcall[0][0] == funcName.split('$')[0] or not funcName.split('$')[1] == "inh":
						continue
					## check for parameters being correct
					if not len(argPossibleTypes) == len(self.classes[-1].funcParam[funcIndex]):
						continue
					isMatch = True
					for parameterIndex, parameterType in enumerate(self.classes[-1].funcParam[funcIndex]):
						if not parameterType in argPossibleTypes[parameterIndex]:
							isMatch = False
							break
						
					if isMatch:
						functionName += funcName
						break

			if functionName == "":
				self.error(f"No function {ctx.func.fcall[0][0]} found in class {self.classes[-1].name}.", ctx.start.line)

			self.replaceFunctions.append([ctx.f[1], functionName])


	## factor and direct_call_stat need work on listener when functions are to be recognized only
	def enterFactor(self, ctx:oosParser.FactorContext):
		self.function_helper(ctx)

	def enterDirect_call_stat(self, ctx:oosParser.Direct_call_statContext):
		self.function_helper(ctx)