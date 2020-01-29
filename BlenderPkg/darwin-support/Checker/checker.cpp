#include <iostream>
#include <fstream>
#include <string>
#include "formSelect.h"

using namespace std;

ofstream logfile;
ostream* outmsg;

int main(int argc, const char *argv[])
{
	outmsg = &cout;
	logfile.open("log.txt");

	formSelect fS=formSelect();
	fS.formSelect_Shown();
}
