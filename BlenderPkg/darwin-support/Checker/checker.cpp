/**********************************************************************
* Copyright 2020 Advanced Micro Devices, Inc
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
* 
*     http://www.apache.org/licenses/LICENSE-2.0
* 
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
********************************************************************/
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
