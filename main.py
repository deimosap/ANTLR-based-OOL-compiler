import sys
from antlr4 import *
from oosLexer import oosLexer
from oosParser import oosParser 
from oosListener import oosListener
## import of myListener
from myoosListener import *

def main(argv):
	input_stream = FileStream(argv[1])
	lexer = oosLexer(input_stream)
	stream = CommonTokenStream(lexer)
	parser = oosParser(stream)
	tree = parser.startRule()
	myListeners = CCodeTranslator()
	walker = ParseTreeWalker()
	walker.walk(myListeners, tree)
	
	with open('output.c', "w") as f:
		for string in myListeners.generated_code:
			f.write(string)
	
if __name__ == '__main__':
	main(sys.argv)
