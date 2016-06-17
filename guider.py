#!/usr/bin/python

__author__ = "Peace Lee"
__copyright__ = "Copyright 2015, guider"
__credits__ = "Peace Lee"
__license__ = "GPLv2"
__version__ = "2.0.0"
__maintainer__ = "Peace Lee"
__email__ = "iipeace5@gmail.com"





try:
    import re
    import sys
    import signal
    import time
    import os
    import shutil
    import gc
    import imp
except ImportError, e:
    SystemInfo.printError("Fail to import default libs because %s" % e)
    sys.exit(0)

try:
    import ctypes
    from ctypes import *
    from ctypes.util import find_library
except:
    None





class ConfigInfo:
    # Define color #
    WARNING = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    SPECIAL = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


    # Define signal #
    sigList = [
           'SIGHUP', # 1 #
           'SIGINT',
           'SIGQUIT',
           'SIGILL',
           'SIGTRAP',
           'SIGABRT',
           'SIGIOT',
           'SIGBUS',
           'SIGFPE',
           'SIGKILL', # 9 #
           'SIGUSR1',
           'SIGSEGV',
           'SIGUSR2',
           'SIGPIPE',
           'SIGALRM',
           'SIGTERM', # 15 #
           'SIGSTKFLT',
           'SIGCHLD', # 17 #
           'SIGCONT',
           'SIGSTOP',
           'SIGTSTP',
           'SIGTTIN',
           'SIGTTOU',
           'SIGURG',
           'SIGXCPU',
           'SIGXFSZ',
           'SIGVTALRM',
           'SIGPROF',
           'SIGWINCH',
           'SIGIO',
           'SIGPWR',
           'SIGSYS' # 32 #
            ]

    taskChainEnable = None

    @staticmethod
    def readProcData(tid, file, num):
        file = '/proc/'+ tid + '/' + file

        try: f = open(file, 'r')
        except:
            SystemInfo.printError("Open %s" % (file))
            return None

        if num == 0: return f.readline().replace('\n','')
        else: return f.readline().replace('\n','').split(' ')[num - 1]



    @staticmethod
    def openConfFile(file):
        file += '.tc'
        if os.path.isfile(file) == True:
            SystemInfo.printWarning("%s already exist, make new one" % (file))

        try: fd = open(file, 'wt')
        except:
            SystemInfo.printError("Fail to open %s" % (file))
            return None

        return fd




    @staticmethod
    def writeConfData(fd, line):
        if fd == None:
            SystemInfo.printError("Fail to get file descriptor")
            return None

        fd.write(line)





class FunctionInfo:
    def __init__(self, logFile):
        self.cpuEnabled = False
        self.memEnabled = False
        self.ioEnabled = False

        self.sort = 'sym'
        self.curMode = ''
        self.prevMode = ''

        self.startTime = '0'
        self.finishTime = '0'
        self.totalTime = 0
        self.totalTick = 0
        self.prevTime = '0'
        self.prevTid = '0'
        self.prevComm = '0'

        self.nowEvent = None
        self.savedEvent = None
        self.nestedEvent = None
        self.nowCnt= 0
        self.savedCnt = 0
        self.nestedCnt = 0
        self.nested = 0

        self.periodicEventCnt = 0
        self.periodicContEventCnt = 0
        self.periodicEventInterval = 0
        self.periodicEventTotal = 0
        self.pageEventCnt = 0
        self.pageUsageCnt = 0
        self.blockEventCnt = 0
        self.blockUsageCnt = 0

        self.mapData = []
        self.posData = {}
        self.userSymData = {}
        self.kernelSymData = {}
        self.threadData = {}
        self.userCallData = [] # [userLastPos, stack[], pageCnt, blockCnt] #
        self.kernelCallData = [] # [userLastPos, stack[], pageCnt, blockCnt] #

        self.init_threadData = \
                {'comm': '', 'tgid': '-'*5, 'target': False, 'cpuTick': int(0), 'die': False}
        self.init_posData = \
                {'symbol': '', 'binary': '', 'origBin': '', 'offset': hex(0), 'posCnt': int(0), 'totalCnt': int(0), \
                'src': '', 'blockCnt': int(0), 'pageCnt': int(0)}
        self.init_SymData = \
                {'pos': '', 'origBin': '', 'cnt': int(0), 'blockCnt': int(0), 'pageCnt': int(0), 'stack': None, 'symStack': None} \
                # stack = [cpuCnt, stack[], pageCnt, blockCnt] #

        # Open log file #
        try: logFd = open(logFile, 'r')
        except:
            SystemInfo.printError("Fail to open %s to create callstack information" % logFile)
            sys.exit(0)

        # Get binary and offset info #
        lines = logFd.readlines()

        # Save data and exit if file is set #
        SystemInfo.saveDataAndExit(lines)

        # Check target thread setting #
        if len(SystemInfo.showGroup) != 1:
            SystemInfo.printError("wrong option with -f, use -g option with only one tid / comm / nothing")
            sys.exit(0)
        else:
            self.target = SystemInfo.showGroup[0]

        # Check addr2line path #
        if SystemInfo.addr2linePath is None:
            SystemInfo.printError("Fail to find addr2line, use also -l option with the path of addr2line")
            sys.exit(0)
        else:
            for path in SystemInfo.addr2linePath:
                if os.path.isfile(path) is False:
                    SystemInfo.printError("Fail to find addr2line, use also -l option with the path of addr2line")
                    sys.exit(0)

        # Check root path #
        if SystemInfo.rootPath is None:
            SystemInfo.printError("Fail to recognize root path for target, use also -j option with the path of root")
            sys.exit(0)

        # Register None pos #
        self.posData['0'] = dict(self.init_posData)

        # Parse logs #
        SystemInfo.totalLine = len(lines)
        self.parseLogs(lines, SystemInfo.showGroup[0])

        # Check whether data of target thread is collected or nothing #
        if len(self.userCallData) == 0 and len(self.kernelCallData) == 0 and len(self.target) != 0:
            SystemInfo.printError("No collected data related to %s" % self.target)
            sys.exit(0)
        elif len(self.userCallData) == 1 and self.userCallData[0][0] == '0':
            SystemInfo.printError("No traced user stack data related to %s, apply kernel patch" % self.target)
            sys.exit(0)

        # Get symbols from call address #
        self.getSymbols()

        # Merge callstacks by symbol and address #
        self.mergeStacks()



    def mergeStacks(self):
        # Merge user call data by symbol or address #
        for val in self.userCallData:
            pos = val[0]
            stack = val[1]
            pageCnt = val[2]
            blockCnt = val[3]
            targetStack = []

            try:
                # No symbol related to last pos #
                if self.posData[pos]['symbol'] == '': 
                    self.posData[pos]['symbol'] == pos
                    sym = pos
                else: 
                    sym = self.posData[pos]['symbol']
            except: continue

            # Make symbol table of last pos in stack #
            try: self.userSymData[sym]
            except:
                self.userSymData[sym] = dict(self.init_SymData)
                self.userSymData[sym]['stack'] = []
                self.userSymData[sym]['symStack'] = []
                self.userSymData[sym]['pos'] = pos
                self.userSymData[sym]['origBin'] = self.posData[pos]['origBin']

            # periodic event such as tick #
            if pageCnt == 0 and blockCnt == 0:
                self.userSymData[sym]['cnt'] += 1
                cpuCnt = 1
            # memory or block related event #
            else:
                cpuCnt = 0
                self.userSymData[sym]['pageCnt'] += pageCnt
                self.userSymData[sym]['blockCnt'] += blockCnt

            # Set target stack #
            if self.sort is 'sym':
                tempSymStack = []
                # Make temporary symbol stack to merge stacks by symbol #
                for addr in stack:
                    tempSym = self.posData[addr]['symbol']

                    # Ignore this function if there is no symbol #
                    if SystemInfo.showAll is False and \
                            tempSym == addr or tempSym == self.posData[addr]['offset']:
                                continue

                    # No symbol data #
                    if tempSym == '': 
                        if self.posData[addr]['origBin'] == '??':
                            tempSym = '%x' % int(self.posData[addr]['pos'], 16)
                        else:
                            tempSym = '%x' % int(self.posData[addr]['offset'], 16)

                    try: self.userSymData[tempSym]
                    except:
                        self.userSymData[tempSym] = dict(self.init_SymData)
                        self.userSymData[tempSym]['stack'] = []
                        self.userSymData[tempSym]['symStack'] = []
                        self.userSymData[tempSym]['pos'] = addr
                        self.userSymData[tempSym]['origBin'] = self.posData[addr]['origBin']

                    tempSymStack.append(tempSym)

                # Switch input stack to symbol stack #
                stack = tempSymStack
                targetStack = self.userSymData[sym]['symStack']
            elif self.sort is 'pos':
                targetStack = self.userSymData[sym]['stack']

            # First stack related to this symbol #
            if len(targetStack) == 0:
                targetStack.append([cpuCnt, stack, pageCnt, blockCnt])
            else:
                found = False

                # Find same stack by pos in stack list #
                for stackInfo in targetStack:
                    # Found it #
                    if len(list(set(stack) - set(stackInfo[1]))) == 0 and \
                            len(list(set(stackInfo[1]) - set(stack))) == 0:
                        stackInfo[2] += pageCnt
                        stackInfo[3] += blockCnt
                        stackInfo[0] += cpuCnt
                        found = True
                        break
                # New stack related to this symbol #
                if found == False:
                    targetStack.append([cpuCnt, stack, pageCnt, blockCnt])

        # Merge kernel call data by address #
        for val in self.kernelCallData:
            pos = val[0]
            stack = val[1]
            pageCnt = val[2]
            blockCnt = val[3]

            try:
                # No symbol related to last pos #
                if self.posData[pos]['symbol'] == '': 
                    self.posData[pos]['symbol'] == pos
                    sym = pos
                else: 
                    sym = self.posData[pos]['symbol']
            except: continue

            try: self.kernelSymData[sym]
            except:
                self.kernelSymData[sym] = dict(self.init_SymData)
                self.kernelSymData[sym]['stack'] = []
                self.kernelSymData[sym]['pos'] = pos

            # If no page and no block then this is periodic event for sampling #
            if pageCnt == 0 and blockCnt == 0:
                self.kernelSymData[sym]['cnt'] += 1
                cpuCnt = 1
            else:
                cpuCnt = 0
                self.kernelSymData[sym]['pageCnt'] += pageCnt
                self.kernelSymData[sym]['blockCnt'] += blockCnt

            # First stack related to this symbol #
            if len(self.kernelSymData[sym]['stack']) == 0:
                self.kernelSymData[sym]['stack'].append([cpuCnt, stack, pageCnt, blockCnt])
            else:
                found = False
                for stackInfo in self.kernelSymData[sym]['stack']:
                    # Found same stack  in stack list #
                    if len(list(set(stack) - set(stackInfo[1]))) == 0 and \
                            len(list(set(stackInfo[1]) - set(stack))) == 0:
                        stackInfo[2] += pageCnt
                        stackInfo[3] += blockCnt
                        stackInfo[0] += cpuCnt
                        found = True
                        break
                # New stack related to this symbol #
                if found == False:
                    self.kernelSymData[sym]['stack'].append([cpuCnt, stack, pageCnt, blockCnt])



    def getSymbols(self):
        binPath = ''
        offsetList = []

        # Set alarm handler to handle hanged addr2line #
        signal.signal(signal.SIGALRM, SystemInfo.timerHandler)

        # Get symbols and source pos #
        for idx, value in sorted(self.posData.items(), key=lambda e: e[1]['binary'], reverse=True):
            if value['binary'] == '':
                # user pos without offset #
                if value['symbol'] == '' or value['symbol'] == '??': 
                    # toDo: find binary and symbol of pos #
                    value['binary'] = '??'
                    value['origBin'] = '??'
                    value['symbol'] = idx
                continue

            # Get symbols from address list of previous binary #
            if binPath != value['binary']:
                if binPath != '':
                    # Get symbols #
                    self.getSymbolInfo(binPath, offsetList)
                    offsetList = []

                if value['offset'] == hex(0): offsetList.append(idx)
                else: offsetList.append(value['offset'])

                # Set new binPath to find symbol from address #
                binPath = value['binary']
            # add address to offsetList #
            else:
                # not relocatable binary #
                if value['offset'] == hex(0):
                    offsetList.append(idx)
                # relocatable binary #
                else:
                    offsetList.append(value['offset'])

        # Get symbols and source path from last binary #
        if binPath != '': self.getSymbolInfo(binPath, offsetList)



    def getSymbolInfo(self, binPath, offsetList):
        try:
            import subprocess
        except ImportError, e:
            SystemInfo.printError("Fail to import because %s" % e)
            sys.exit(0)

        # Recognize binary type #
        relocated = SystemInfo.isRelocatableFile(binPath)

        # No file exist #
        if os.path.isfile(binPath) == False:
            SystemInfo.printWarning("Fail to find %s" % binPath)
            for addr in offsetList: 
                if relocated is False:
                    self.posData[addr]['symbol'] = 'NoFile'
                    self.posData[addr]['src'] = 'NoFile'
                else:
                    for idx, value in sorted(self.posData.items(), key=lambda e: e[1]['binary'], reverse=True):
                        if value['binary'] == binPath and value['offset'] == hex(int(addr, 16)):
                            self.posData[idx]['symbol'] = 'NoFile'
                            self.posData[idx]['src'] = 'NoFile'
                            break
            return

        for path in SystemInfo.addr2linePath:
            # Set addr2line command #
            args = [path, "-C", "-f", "-a", "-e", binPath]

            # Prepare for variable to use as index #
            offset = 0
            listLen = len(offsetList)
            maxArg = 512

            # Get symbol by address of every maxArg elements in list #
            while offset < listLen:
                # Launch addr2line #
                proc = subprocess.Popen(args + offsetList[offset:offset+maxArg-1], \
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                # Increase offset count in address list #
                offset += maxArg

                try:
                    # Set alarm to handle hanged addr2line #
                    signal.alarm(5)
                    # Wait for addr2line to finish its job #
                    proc.wait()
                    # Cancel alarm after addr2line respond #
                    signal.alarm(0)
                except:
                    SystemInfo.printWarning('No response of addr2line')
                    continue

                while True:
                    # Get return of addr2line #
                    addr = proc.stdout.readline().replace('\n', '')[2:]
                    symbol = proc.stdout.readline().replace('\n', '')
                    src = proc.stdout.readline().replace('\n', '')

                    err = proc.stderr.readline().replace('\n', '')
                    if len(err) > 0:
                        SystemInfo.printWarning(err[err.find(':') + 2:])

                    # End of return #
                    if not addr: break

                    if symbol == '??': symbol = addr

                    # Check whether the file is relocatable or not #
                    if relocated is False:
                        savedSymbol = self.posData[addr]['symbol']
                        # Check whether saved symbol found by previous addr2line is right #
                        if savedSymbol == '' or savedSymbol == addr or savedSymbol[0] == '$':
                            self.posData[addr]['symbol'] = symbol
                            self.posData[addr]['src'] = src
                    else:
                        inBinArea = False
                        for idx, value in sorted(self.posData.items(), key=lambda e: e[1]['binary'], reverse=True):
                            if value['binary'] == binPath:
                                inBinArea = True
                                if value['offset'] == hex(int(addr, 16)):
                                    savedSymbol = self.posData[idx]['symbol']
                                    if savedSymbol == '' or savedSymbol == addr or savedSymbol[0] == '$':
                                        self.posData[idx]['symbol'] = symbol
                                        self.posData[idx]['src'] = src
                                        break
                            elif inBinArea is True:
                                break



    def parseLogs(self, lines, desc):
        recStat = False
        userLastPos = ''
        userCallStack = []
        kernelLastPos = ''
        kernelCallStack = []
        bakKernelLastPos = ''
        bakKernelCallStack = []

        for l in lines:
            SystemInfo.logSize += len(l)
            SystemInfo.curLine += 1
            SystemInfo.dbgEventLine += 1

            ret = self.parseStackLog(l, desc)

            if self.savedEvent is None:
                self.savedEvent = self.nowEvent

            # Save full stack to callData table #
            if ret is True:
                # stack of kernel thread #
                if self.prevMode != self.curMode == 'kernel' and len(userCallStack) == 0 and len(kernelCallStack) > 0:
                    # Set userLastPos to None #
                    userLastPos = '0'
                    userCallStack.append('0')

                # complicated situation ;( #
                elif self.prevMode == self.curMode:
                    # previous user stack loss or nested interval #
                    if self.curMode is 'kernel':
                        # nested interval #
                        if self.nowEvent is 'C':
                            # Backup kernel stack #
                            bakKernelLastPos = kernelLastPos
                            bakKernelCallStack = kernelCallStack

                            # Initialize both stacks #
                            userLastPos = '0'
                            userCallStack = []
                            kernelLastPos = '0'
                            kernelCallStack = []
                        # previous user stack loss #
                        else:
                            # Set userLastPos to None #
                            userLastPos = '0'
                            userCallStack.append('0')
                    # nested interval #
                    elif self.curMode is 'user':
                        # Swap event and cnt #
                        tempEvent = self.nowEvent
                        self.nowEvent = self.savedEvent
                        self.savedEvent = tempEvent
                        tempCnt = self.nowCnt
                        self.nowCnt = self.savedCnt
                        self.savedCnt = tempCnt

                # Save both stacks of previous event before starting to record new kernel stack #
                if (len(userCallStack) > 0 and userLastPos != '') and (len(kernelCallStack) > 0 and kernelLastPos != ''):
                    del kernelCallStack[0], userCallStack[0]

                    # Check whether there is nested event or not #
                    if self.nested > 0:
                        targetEvent = self.nestedEvent
                        targetCnt = self.nestedCnt

                        # Swap event and cnt #
                        tempEvent = self.nowEvent
                        self.nowEvent = self.savedEvent
                        self.savedEvent = tempEvent
                        tempCnt = self.nowCnt
                        self.nowCnt = self.savedCnt
                        self.savedCnt = tempCnt
                    else:
                        targetEvent = self.savedEvent
                        targetCnt = self.savedCnt

                    # Save full stack of previous event #
                    if targetEvent == 'C':
                        self.periodicEventCnt += 1

                        self.kernelCallData.append([kernelLastPos, kernelCallStack, 0, 0])
                        self.userCallData.append([userLastPos, userCallStack, 0, 0])
                    elif targetEvent == 'MA':
                        self.pageEventCnt += 1
                        self.pageUsageCnt += targetCnt
                        self.posData[kernelLastPos]['pageCnt'] += targetCnt
                        self.posData[userLastPos]['pageCnt'] += targetCnt

                        self.kernelCallData.append([kernelLastPos, kernelCallStack, targetCnt, 0])
                        self.userCallData.append([userLastPos, userCallStack, targetCnt, 0])

                        self.savedCnt = 0
                    elif targetEvent == 'B':
                        self.blockEventCnt += 1
                        self.blockUsageCnt += targetCnt
                        self.posData[kernelLastPos]['blockCnt'] += targetCnt
                        self.posData[userLastPos]['blockCnt'] += targetCnt

                        self.kernelCallData.append([kernelLastPos, kernelCallStack, 0, targetCnt])
                        self.userCallData.append([userLastPos, userCallStack, 0, targetCnt])

                        self.savedCnt = 0
                    else:
                        self.savedCnt = 0

                    # Recover previous kernel stack after finishing nested event #
                    if self.prevMode == self.curMode == 'user' and bakKernelLastPos != '0':
                        kernelLastPos = bakKernelLastPos
                        kernelCallStack = bakKernelCallStack
                        bakKernelLastPos = '0'
                        bakKernelCallStack = []
                    else:
                        kernelLastPos = ''
                        kernelCallStack = []

                    userLastPos = ''
                    userCallStack = []
                    self.nestedEvent = ''
                    self.nestedCnt = 0

                # On stack recording switch #
                recStat = True
            # Ignore this log because its not event or stack info related to target thread #
            elif ret is False:
                recStat = False
                continue
            # Save pos into target stack #
            elif recStat is True:
                (pos, path, offset) = ret

                if self.nested > 0:
                    targetEvent = self.savedEvent
                else:
                    targetEvent = self.nowEvent

                # Register pos #
                try: self.posData[pos]
                except: self.posData[pos] = dict(self.init_posData)

                # user mode #
                if self.curMode is 'user':
                    # Set path #
                    if path is not None:
                        self.posData[pos]['origBin'] = path
                        self.posData[pos]['binary'] = SystemInfo.rootPath + path
                        self.posData[pos]['binary'] = self.posData[pos]['binary'].replace('//', '/')

                        # Set offset #
                        if offset is not None:
                            if SystemInfo.isRelocatableFile(path) is True:
                                self.posData[pos]['offset'] = offset

                    # Save pos #
                    if len(userCallStack) == 0:
                        userLastPos = pos
                        if targetEvent == 'C':
                            self.posData[pos]['posCnt'] += 1

                    userCallStack.append(pos)
                # kernel mode #
                elif self.curMode is 'kernel':
                    # Save pos #
                    if len(kernelCallStack) == 0:
                        kernelLastPos = pos
                        if targetEvent  == 'C':
                            self.posData[pos]['posCnt'] += 1

                    self.posData[pos]['symbol'] = path

                    kernelCallStack.append(pos)
                # wrong mode #
                else:
                    SystemInfo.printWarning('wrong current mode %s' % self.curMode)

                # Increase total call count #
                if self.nowEvent == 'C':
                    self.posData[pos]['totalCnt'] += 1



    def parseStackLog(self, string, desc):
        SystemInfo.printProgress()

        # Filter for event #
        if SystemInfo.tgidEnable is True:
            m = re.match('^\s*(?P<comm>.+)-(?P<thread>[0-9]+)\s+\(\s*(?P<tgid>\S+)\)\s+\[(?P<core>[0-9]+)\]\s+(?P<time>\S+):\s+(?P<func>\S+)(?P<etc>.+)', string)
        else:
            m = re.match('^\s*(?P<comm>.+)-(?P<thread>[0-9]+)\s+\[(?P<core>[0-9]+)\]\s+(?P<time>\S+):\s+(?P<func>\S+)(?P<etc>.+)', string)

        if m is not None:
            d = m.groupdict()

            # Set time #
            if self.startTime == '0':
                self.startTime = d['time']
            else:
                self.finishTime = d['time']

            # Make thread entity #
            thread = d['thread']
            try: self.threadData[thread]
            except:
                self.threadData[thread] = dict(self.init_threadData)
                self.threadData[thread]['comm'] = d['comm']

            # Calculate a total of cpu usage #
            if d['func'] == "hrtimer_start:" and d['etc'].rfind('tick_sched_timer') != -1:
                self.totalTick += 1
                self.threadData[thread]['cpuTick'] += 1

                # Set interval #
                if self.periodicEventCnt > 0 and (self.prevComm == d['comm'] or self.prevTid == thread):
                    diff = float(d['time']) - float(self.prevTime)
                    self.periodicEventTotal += diff
                    self.periodicContEventCnt += 1
                    self.periodicEventInterval = round(self.periodicEventTotal / self.periodicContEventCnt, 3)

                self.prevComm = d['comm']
                self.prevTid = thread
                self.prevTime = d['time']

                # Set max core to calculate cpu usage of thread #
                core = int(d['core'])
                if SystemInfo.maxCore < core:
                    SystemInfo.maxCore = core
            elif d['func'] == "sched_process_free:":
                m = re.match('^\s*comm=(?P<comm>.*)\s+pid=(?P<pid>[0-9]+)', d['etc'])
                if m is not None:
                    p = m.groupdict()

                    pid = p['pid']

                    try: self.threadData[pid]
                    except:
                        self.threadData[pid] = dict(self.init_threadData)
                        self.threadData[pid]['comm'] = p['comm']

                    self.threadData[pid]['die'] = True

            # Save tgid(pid) #
            if SystemInfo.tgidEnable is True:
                self.threadData[thread]['tgid'] = d['tgid']

            # tid filter #
            if len(desc) == 0:
                return False
            if int(desc) != int(d['thread']) and d['comm'].rfind(desc) == -1: 
                return False
            else:
                self.threadData[thread]['target'] = True

            # ToDo: find shorter periodic event for sampling #
            # cpu tick event #
            if d['func'] == "hrtimer_start:" and d['etc'].rfind('tick_sched_timer') != -1:
                self.cpuEnabled = True
                self.nestedEvent = self.savedEvent
                self.savedEvent = self.nowEvent
                self.nowEvent = 'C'

                self.nestedCnt = self.savedCnt
                self.savedCnt = self.nowCnt
                self.nowCnt = 0

                self.nested += 1

                return False

            # ToDo: make memory map and add mm_page_free event #
            # memory allocation event #
            elif d['func'] == "mm_page_alloc:":
                m = re.match('^\s*page=(?P<page>\S+)\s+pfn=(?P<pfn>[0-9]+)\s+order=(?P<order>[0-9]+)\s+migratetype=(?P<mt>[0-9]+)\s+gfp_flags=(?P<flags>\S+)', d['etc'])
                if m is not None:
                    d = m.groupdict()

                    self.memEnabled = True
                    self.nestedEvent = self.savedEvent
                    self.savedEvent = self.nowEvent
                    self.nowEvent = 'MA'

                    self.nestedCnt = self.savedCnt
                    self.savedCnt = self.nowCnt
                    self.nowCnt = pow(2, int(d['order']))

                    self.nested += 1

                return False

            # block request event #
            elif d['func'] == "block_bio_remap:":
                m = re.match('^\s*(?P<major>[0-9]+),(?P<minor>[0-9]+)\s*(?P<operation>\S+)\s*(?P<address>\S+)\s+\+\s+(?P<size>[0-9]+)', d['etc'])
                if m is not None:
                    d = m.groupdict()

                    if d['operation'][0] == 'R':
                        self.ioEnabled = True
                        self.nestedEvent = self.savedEvent
                        self.savedEvent = self.nowEvent
                        self.nowEvent = 'B'

                        self.nestedCnt = self.savedCnt
                        self.savedCnt = self.nowCnt
                        self.nowCnt = int(d['size'])

                        self.nested += 1

                return False

            # starting to record user stack #
            elif d['func'] == "<user": 
                self.prevMode = self.curMode
                self.curMode = 'user'
                return True

            # starting to record kernel stack #
            elif d['func'] == "<stack":
                self.prevMode = self.curMode
                self.curMode = 'kernel'
                self.nested -= 1
                return True

            # user-define event #
            elif SystemInfo.targetEvent is not None and d['func'] == SystemInfo.targetEvent + ':':
                self.cpuEnabled = True
                self.savedEvent = self.nowEvent
                self.nowEvent = 'C'
                self.savedCnt = self.nowCnt
                self.nowCnt = 0

                return False

            # ignore event #
            else: 
                self.nestedEvent = self.savedEvent
                self.savedEvent = self.nowEvent
                self.nowEvent = 'I'

                self.nestedCnt = self.savedCnt
                self.savedCnt = self.nowCnt
                self.nowCnt = 0

                self.nested += 1

                return False

        # parse call stack #
        else:
            pos = string.find('=>  <')
            noPos = string.find('??')
            m = re.match(' => (?P<path>.+)\[\+0x(?P<offset>.\S*)\] \<(?P<pos>.\S+)\>', string)

            # exist path, offset, pos #
            if m is not None:
                d = m.groupdict()
                return (d['pos'], d['path'], hex(int(d['offset'], 16)))
            # exist only pos #
            elif pos >= 0:
                return (string[pos+5:len(string)-2], None, None)
            # exist nothing #
            elif noPos >= 0:
                return ('0', None, None)
            else:
                m = re.match(' => (?P<symbol>.+) \<(?P<pos>.\S+)\>', string)
                # exist symbol, pos #
                if m is not None:
                    d = m.groupdict()
                    return (d['pos'], d['symbol'], None)
                # garbage log #
                else: 
                    return False



    def parseMapLine(self, string):
        m = re.match('^(?P<startAddr>.\S+)-(?P<endAddr>.\S+) (?P<permission>.\S+) (?P<offset>.\S+) (?P<devid>.\S+) (?P<inode>.\S+)\s*(?P<binName>.\S+)', string)
        if m is not None:
            d = m.groupdict()
            self.mapData.append({'startAddr': d['startAddr'], 'endAddr': d['endAddr'], 'binName': d['binName']})



    def getBinInfo(self, addr):
        if SystemInfo.rootPath is None:
            SystemInfo.printError("Fail to recognize root path for target, use also -j option with the path of root")
            sys.exit(0)

        for data in self.mapData:
            if int(data['startAddr'], 16) <= int(addr, 16) and int(data['endAddr'], 16) >= int(addr, 16):
                if SystemInfo.isRelocatableFile(data['binName']) is True:
                    # Return full path and offset about address in mapping table
                    return SystemInfo.rootPath + data['binName'], hex(int(addr,16) - int(data['startAddr'],16))
                else:
                    return SystemInfo.rootPath + data['binName'], hex(int(addr,16))
        SystemInfo.printWarning("Fail to get the binary info of %s in mapping table" % addr)



    def printUsage(self):
        targetFound = False
        self.totalTime = float(self.finishTime) - float(self.startTime)

        # Print title #
        SystemInfo.printTitle()

        # Print profiled thread list #
        SystemInfo.pipePrint("[%s] [ %s: %0.3f ] [ Running: %d ] [ LogSize: %d KB ] [ Keys: Foward/Back/Save/Quit ]" % \
        ('Function Info', 'Elapsed time', round(self.totalTime, 7), len(self.threadData), SystemInfo.logSize / 1024))
        SystemInfo.pipePrint(twoLine)
        SystemInfo.pipePrint("{0:_^16}|{1:_^7}|{2:_^7}|{3:_^10}|{4:_^7}|{5:_^5}|".\
                format("Name", "Tid", "Pid", "Target", "CPU", "DIE"))
        SystemInfo.pipePrint(twoLine)

        for idx, value in sorted(self.threadData.items(), key=lambda e: e[1]['cpuTick'], reverse=True):
            targetMark = ''
            dieMark = ''

            if value['target'] is True:
                if targetFound is True:
                    SystemInfo.printWarning("Target thread should be only one, otherwise profile result will be incorrect")
                targetMark = '*'
                targetFound = True

            cpuPer = float(value['cpuTick']) / float(self.totalTick) * 100
            if cpuPer < 1 and SystemInfo.showAll is False:
                break

            if value['die'] is True:
                dieMark = 'v'

            SystemInfo.pipePrint("{0:16}|{1:^7}|{2:^7}|{3:^10}|{4:6.1f}%|{5:^5}|".\
                    format(value['comm'], idx, value['tgid'], targetMark, cpuPer, dieMark))

        SystemInfo.pipePrint(oneLine + '\n\n\n')

        # Exit because of no target #
        if len(self.target) == 0: 
            sys.exit(0)

        # Print profiled thread list #
        self.printCpuUsage()
        self.printMemUsage()
        self.printBlockUsage()



    def printCpuUsage(self):
        # Print cpu usage in user space #
        SystemInfo.clearPrint()
        if SystemInfo.targetEvent is None:
            SystemInfo.pipePrint('[CPU Info] [Cnt: %d] [Interval: %dms] (USER)' % \
                    (self.periodicEventCnt, self.periodicEventInterval * 1000))
        else:
            SystemInfo.pipePrint('[EVENT Info] [Event: %s] [Cnt: %d] (USER)' % (SystemInfo.targetEvent, self.periodicEventCnt))

        SystemInfo.pipePrint(twoLine)
        SystemInfo.pipePrint("{0:_^9}|{1:_^32}|{2:_^48}|{3:_^62}".format("Usage", "Function", "Binary", "Source"))
        SystemInfo.pipePrint(twoLine)

        for idx, value in sorted(self.userSymData.items(), key=lambda e: e[1]['cnt'], reverse=True):
            if self.cpuEnabled is False or value['cnt'] == 0: break

            cpuPer = round(float(value['cnt']) / float(self.periodicEventCnt) * 100, 1)
            if cpuPer < 1 and SystemInfo.showAll is False:
                break

            SystemInfo.pipePrint("{0:7}% |{1:^32}|{2:48}|{3:52}".format(cpuPer, idx, \
                    self.posData[value['pos']]['origBin'], self.posData[value['pos']]['src']))

            # Set target stack #
            targetStack = []
            if self.sort is 'sym':
                targetStack = value['symStack']
            elif self.sort is 'pos':
                targetStack = value['stack']

            # Sort by usage #
            targetStack.sort(reverse=True)

            # Merge and Print symbols in stack #
            for stack in targetStack:
                cpuCnt = stack[0]
                subStack = list(stack[1])

                if cpuCnt == 0: break

                if len(subStack) == 0: continue
                else:
                    # Make stack info by symbol for print #
                    symbolStack = ''
                    if self.sort is 'sym':
                        for sym in subStack:
                            symbolStack +=  ' <- ' + sym + ' [' + self.userSymData[sym]['origBin'] + ']'
                    elif self.sort is 'pos':
                        for pos in subStack:
                            # No symbol so that just print pos #
                            if self.posData[pos]['symbol'] == '':
                                symbolStack +=  ' <- ' + hex(int(pos, 16)) + ' [' + self.posData[pos]['origBin'] + ']'
                            # Print symbol #
                            else:
                                symbolStack +=  ' <- ' + self.posData[pos]['symbol'] + ' [' + self.posData[pos]['origBin'] + ']'

                SystemInfo.pipePrint("\t\t |{0:7}% |{1:32}" \
                        .format(round(float(cpuCnt) / float(value['cnt']) * 100, 1), symbolStack))

            SystemInfo.pipePrint(oneLine)
        SystemInfo.pipePrint('\n\n')

        # Print cpu usage in kernel space #
        SystemInfo.clearPrint()
        if SystemInfo.targetEvent is None:
                SystemInfo.pipePrint('[CPU Info] [Cnt: %d] [Interval: %dms] (KERNEL)' % \
                        (self.periodicEventCnt, self.periodicEventInterval * 1000))
        else:
            SystemInfo.pipePrint('[EVENT Info] [Event: %s] [Cnt: %d] (KERNEL)' % (SystemInfo.targetEvent, self.periodicEventCnt))

        SystemInfo.pipePrint(twoLine)
        SystemInfo.pipePrint("{0:_^9}|{1:_^32}|{2:_^48}|{3:_^62}".format("Usage", "Function", "Binary", "Source"))
        SystemInfo.pipePrint(twoLine)

        # Make exception list to remove a redundant part of stack #
        exceptList = {}
        for pos, value in self.posData.items():
            if value['symbol'] == '__irq_usr' or value['symbol'] == '__irq_svc' or \
                value['symbol'] == '__hrtimer_start_range_ns' or value['symbol'] == 'hrtimer_start_range_ns' or \
                value['symbol'] == 'apic_timer_interrupt':
                try: exceptList[pos]
                except: exceptList[pos] = dict()

        # Print cpu usage of stacks #
        for idx, value in sorted(self.kernelSymData.items(), key=lambda e: e[1]['cnt'], reverse=True):
            if self.cpuEnabled is False or value['cnt'] == 0: break

            cpuPer = round(float(value['cnt']) / float(self.periodicEventCnt) * 100, 1)
            SystemInfo.pipePrint("{0:7}% |{1:^32}|{2:48}|{3:52}".format(cpuPer, idx, '', ''))

            # Sort stacks by usage #
            value['stack'].sort(reverse=True)

            # Print stacks by symbol #
            for stack in value['stack']:
                cpuCnt = stack[0]
                subStack = list(stack[1])

                if cpuCnt == 0: break
                else:
                    # Remove a redundant part #
                    for pos, val in exceptList.items():
                        try: del subStack[0:subStack.index(pos)+1]
                        except: None

                if len(subStack) == 0: continue
                else:
                    # Make stack info by symbol for print #
                    symbolStack = ''
                    try:
                        for pos in subStack:
                            if self.posData[pos]['symbol'] == '':
                                symbolStack +=  ' <- ' + hex(int(pos, 16))
                            else:
                                symbolStack +=  ' <- ' + str(self.posData[pos]['symbol'])
                    except: continue

                SystemInfo.pipePrint("\t\t |{0:7}% |{1:32}" \
                        .format(round(float(cpuCnt) / float(value['cnt']) * 100, 1), symbolStack))

            SystemInfo.pipePrint(oneLine)
        SystemInfo.pipePrint('\n\n')



    def printMemUsage(self):
       # Print mem usage in user space #
        SystemInfo.clearPrint()
        SystemInfo.pipePrint('[MEM Info] [Size: %dKB] [Cnt: %d] (USER)' % \
                (self.pageUsageCnt * 4, self.pageEventCnt))

        SystemInfo.pipePrint(twoLine)
        SystemInfo.pipePrint("{0:_^9}|{1:_^32}|{2:_^48}|{3:_^62}".format("Usage", "Function", "Binary", "Source"))
        SystemInfo.pipePrint(twoLine)

        for idx, value in sorted(self.userSymData.items(), key=lambda e: e[1]['pageCnt'], reverse=True):
            if self.memEnabled is False or value['pageCnt'] == 0: break

            SystemInfo.pipePrint("{0:7}K |{1:^32}|{2:48}|{3:52}".format(value['pageCnt'] * 4, idx, \
                    self.posData[value['pos']]['origBin'], self.posData[value['pos']]['src']))

            # Set target stack #
            targetStack = []
            if self.sort is 'sym':
                targetStack = value['symStack']
            elif self.sort is 'pos':
                targetStack = value['stack']

            # Sort by usage #
            targetStack = sorted(targetStack, key=lambda x:x[2], reverse=True)

            # Merge and Print symbols in stack #
            for stack in targetStack:
                pageCnt = stack[2]
                subStack = list(stack[1])

                if pageCnt == 0: break

                if len(subStack) == 0: continue
                else:
                    # Make stack info by symbol for print #
                    symbolStack = ''
                    if self.sort is 'sym':
                        for sym in subStack:
                            symbolStack +=  ' <- ' + sym + ' [' + self.userSymData[sym]['origBin'] + ']'
                    elif self.sort is 'pos':
                        for pos in subStack:
                            # No symbol so that just print pos #
                            if self.posData[pos]['symbol'] == '':
                                symbolStack +=  ' <- ' + hex(int(pos, 16)) + ' [' + self.posData[pos]['origBin'] + ']'
                            # Print symbol #
                            else:
                                symbolStack +=  ' <- ' + self.posData[pos]['symbol'] + ' [' + self.posData[pos]['origBin'] + ']'

                SystemInfo.pipePrint("\t{0:7}K |{1:32}".format(pageCnt * 4, symbolStack))

            SystemInfo.pipePrint(oneLine)
        SystemInfo.pipePrint('\n\n')

        # Print mem usage in kernel space #
        SystemInfo.clearPrint()
        SystemInfo.pipePrint('[MEM Info] [Size: %dKB] [Cnt: %d] (KERNEL)' % \
                (self.pageUsageCnt * 4, self.pageEventCnt))

        SystemInfo.pipePrint(twoLine)
        SystemInfo.pipePrint("{0:_^9}|{1:_^32}|{2:_^48}|{3:_^62}".format("Usage", "Function", "Binary", "Source"))
        SystemInfo.pipePrint(twoLine)

        # Make exception list to remove a redundant part of stack #
        exceptList = {}
        for pos, value in self.posData.items():
            break
            if value['symbol'] == 'None':
                try: exceptList[pos]
                except: exceptList[pos] = dict()

        # Print mem usage of stacks #
        for idx, value in sorted(self.kernelSymData.items(), key=lambda e: e[1]['pageCnt'], reverse=True):
            if self.memEnabled is False or value['pageCnt'] == 0: break

            SystemInfo.pipePrint("{0:7}K |{1:^32}|{2:48}|{3:52}".format(value['pageCnt'] * 4, idx, '', ''))

            # Sort stacks by usage #
            value['stack'] = sorted(value['stack'], key=lambda x:x[2], reverse=True)

            # Print stacks by symbol #
            for stack in value['stack']:
                pageCnt = stack[2]
                subStack = list(stack[1])

                if pageCnt == 0: continue

                if len(subStack) == 0: continue
                else:
                    # Make stack info by symbol for print #
                    symbolStack = ''
                    try:
                        for pos in subStack:
                            if self.posData[pos]['symbol'] == '':
                                symbolStack +=  ' <- ' + hex(int(pos, 16))
                            else: 
                                symbolStack +=  ' <- ' + str(self.posData[pos]['symbol'])
                    except: continue

                SystemInfo.pipePrint("\t{0:7}K |{1:32}".format(stack[2] * 4, symbolStack))

            SystemInfo.pipePrint(oneLine)
        SystemInfo.pipePrint('\n\n')

    def printBlockUsage(self):
        # Print BLOCK usage in user space #
        SystemInfo.clearPrint()
        SystemInfo.pipePrint('[BLK_RD Info] [Size: %dKB] [Cnt: %d] (USER)' % \
                (self.blockUsageCnt * 0.5, self.blockEventCnt))

        SystemInfo.pipePrint(twoLine)
        SystemInfo.pipePrint("{0:_^9}|{1:_^32}|{2:_^48}|{3:_^62}".format("Usage", "Function", "Binary", "Source"))
        SystemInfo.pipePrint(twoLine)

        for idx, value in sorted(self.userSymData.items(), key=lambda e: e[1]['blockCnt'], reverse=True):
            if self.ioEnabled is False or value['blockCnt'] == 0: break

            SystemInfo.pipePrint("{0:7}K |{1:^32}|{2:48}|{3:52}".format(int(value['blockCnt'] * 0.5), idx, \
                    self.posData[value['pos']]['origBin'], self.posData[value['pos']]['src']))

            # Set target stack #
            targetStack = []
            if self.sort is 'sym':
                targetStack = value['symStack']
            elif self.sort is 'pos':
                targetStack = value['stack']

            # Sort by usage #
            targetStack = sorted(targetStack, key=lambda x:x[3], reverse=True)

            # Merge and Print symbols in stack #
            for stack in targetStack:
                blockCnt = stack[3]
                subStack = list(stack[1])

                if blockCnt == 0: break

                if len(subStack) == 0: continue
                else:
                    # Make stack info by symbol for print #
                    symbolStack = ''
                    if self.sort is 'sym':
                        for sym in subStack:
                            symbolStack +=  ' <- ' + sym + ' [' + self.userSymData[sym]['origBin'] + ']'
                    elif self.sort is 'pos':
                        for pos in subStack:
                            # No symbol so that just print pos #
                            if self.posData[pos]['symbol'] == '':
                                symbolStack +=  ' <- ' + hex(int(pos, 16)) + ' [' + self.posData[pos]['origBin'] + ']'
                            # Print symbol #
                            else:
                                symbolStack +=  ' <- ' + self.posData[pos]['symbol'] + ' [' + self.posData[pos]['origBin'] + ']'

                SystemInfo.pipePrint("\t{0:7}K |{1:32}".format(int(stack[3] * 0.5), symbolStack))

            SystemInfo.pipePrint(oneLine)
        SystemInfo.pipePrint('\n\n')

        # Print BLOCK usage in kernel space #
        SystemInfo.clearPrint()
        SystemInfo.pipePrint('[BLK_RD Info] [Size: %dKB] [Cnt: %d] (KERNEL)' % \
                (self.blockUsageCnt * 0.5, self.blockEventCnt))

        SystemInfo.pipePrint(twoLine)
        SystemInfo.pipePrint("{0:_^9}|{1:_^32}|{2:_^48}|{3:_^62}".format("Usage", "Function", "Binary", "Source"))
        SystemInfo.pipePrint(twoLine)

        # Make exception list to remove a redundant part of stack #
        exceptList = {}
        for pos, value in self.posData.items():
            break
            if value['symbol'] == 'None':
                try: exceptList[pos]
                except: exceptList[pos] = dict()

        # Print BLOCK usage of stacks #
        for idx, value in sorted(self.kernelSymData.items(), key=lambda e: e[1]['blockCnt'], reverse=True):
            if self.ioEnabled is False or value['blockCnt'] == 0: break

            SystemInfo.pipePrint("{0:7}K |{1:^32}|{2:48}|{3:52}".format(int(value['blockCnt'] * 0.5), idx, '', ''))

            # Sort stacks by usage #
            value['stack'] = sorted(value['stack'], key=lambda x:x[3], reverse=True)

            # Print stacks by symbol #
            for stack in value['stack']:
                blockCnt = stack[3]
                subStack = list(stack[1])

                if blockCnt  == 0: continue

                if len(subStack) == 0: symbolStack = '\tNone'
                else:
                    # Make stack info by symbol for print #
                    symbolStack = ''
                    try:
                        for pos in subStack:
                            if self.posData[pos]['symbol'] == '': 
                                symbolStack +=  ' <- ' + hex(int(pos, 16))
                            else: 
                                symbolStack +=  ' <- ' + str(self.posData[pos]['symbol'])
                    except: continue

                SystemInfo.pipePrint("\t{0:7}K |{1:32}".format(int(stack[3] * 0.5), symbolStack))

            SystemInfo.pipePrint(oneLine)
        SystemInfo.pipePrint('\n\n')





class FileInfo:
    condExit = False

    def __init__(self):
        self.libguider = None
        self.libguiderPath = './libguider.so'
        self.procPath = '/proc'

        self.startTime = None
        self.profSuccessCnt = 0
        self.profFailedCnt = 0
        self.procData = {}
        self.fileData = {}

        self.procList = {}
        self.fileList = {}

        self.intervalProcData = []
        self.intervalFileData = []

        self.init_procData = {'tids': None, 'pageCnt': int(0), 'procMap': None}
        self.init_threadData = {'comm': ''}
        self.init_mapData = {'offset': int(0), 'size': int(0), 'pageCnt': int(0), 'fd': None, \
                'totalSize': int(0), 'fileMap': None}

        if len(SystemInfo.showGroup) == 0:
            SystemInfo.printError("wrong option with -m, use -g option with tids / comms")
            sys.exit(0)

        try:
            imp.find_module('ctypes')
        except:
            SystemInfo.printError('Fail to import ctypes module')
            sys.exit(0)

        try:
            # load the library #
            self.libguider = cdll.LoadLibrary(self.libguiderPath)
        except:
            SystemInfo.printError('Fail to open %s' % self.libguiderPath)
            sys.exit(0)

        # set the argument type #
        self.libguider.get_filePageMap.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
        # set the return type #
        self.libguider.get_filePageMap.restype = POINTER(ctypes.c_ubyte)

        self.startTime = time.time()

        while True:
            # scan proc directory and save map information of processes #
            self.scanProcs()

            # merge maps of processes into a integrated file map #
            self.mergeFileMapInfo()

            # get file map info on memory #
            self.getFilePageMaps()

            # fill file map of each processes #
            self.fillFileMaps()

            if SystemInfo.intervalEnable > 0:
                # save previous file usage and initialize variables #
                self.intervalProcData.append(self.procData)
                self.intervalFileData.append(self.fileData)
                self.procData = {}
                self.fileData = {}
                self.profSuccessCnt = 0
                self.profFailedCnt = 0

                # check exit condition for interval profile #
                if FileInfo.condExit is False:
                    signal.pause()
                else:
                    break
            else:
                break

        if SystemInfo.intervalEnable == 0:
            # print total file usage per process #
            self.printUsage()
        else:
            # print file usage per process on timeline #
            self.printIntervalInfo()



    def printUsage(self):
        if len(self.procData) == 0:
            SystemInfo.printError('No process profiled')
            sys.exit(0)
        if len(self.fileData) == 0:
            SystemInfo.printError('No file profiled')
            sys.exit(0)

        # Print title #
        SystemInfo.printTitle()

        # Print proccess list #
        SystemInfo.pipePrint("[%s] [ Process : %d ] [ Keys: Foward/Back/Save/Quit ]" % \
        ('File Info', len(self.procData)))
        SystemInfo.pipePrint(twoLine)
        SystemInfo.pipePrint("{0:_^7}|{1:_^10}|{2:_^16}({3:_^7})".format("Pid", "Size(KB)", "ThreadName", "Tid"))
        SystemInfo.pipePrint(twoLine)

        for pid, val in sorted(self.procData.items(), key=lambda e: int(e[1]['pageCnt']), reverse=True):
            printMsg = "{0:^7}|{1:9} ".format(pid, val['pageCnt'] * SystemInfo.pageSize / 1024)
            for tid, threadVal in sorted(val['tids'].items(), reverse=True):
                printMsg += "|{0:^16}({1:^7})".format(threadVal['comm'], tid)
                SystemInfo.pipePrint(printMsg)
                printMsg = "{0:^7}{1:^11}".format('', '')

        SystemInfo.pipePrint(oneLine + '\n\n\n')

        # Print file list #
        SystemInfo.pipePrint("[%s] [ File: %d ] [ Keys: Foward/Back/Save/Quit ]" % \
        ('File Info', len(self.fileData)))
        SystemInfo.pipePrint(twoLine)
        SystemInfo.pipePrint("{0:_^12}|{1:_^10}|{2:_^5}| {3:6}".\
                format("Memory(KB)", "File(KB)", "%", "Path"))
        SystemInfo.pipePrint(twoLine)

        for fileName, val in sorted(self.fileData.items(), key=lambda e: int(e[1]['pageCnt']), reverse=True):
            memSize = val['pageCnt'] * SystemInfo.pageSize / 1024
            fileSize = ((val['totalSize'] + SystemInfo.pageSize - 1) / SystemInfo.pageSize) * SystemInfo.pageSize / 1024
            per = 0

            if fileSize != 0:
                per = int(int(memSize) / float(fileSize) * 100)

            SystemInfo.pipePrint("{0:11} |{1:9} |{2:5}| {3:6}".\
                    format(memSize, fileSize, per, fileName))

        SystemInfo.pipePrint(oneLine + '\n\n\n')



    def printIntervalInfo(self):
        # Merge proccess info into a global list #
        for procData in self.intervalProcData:
            for pid, procInfo in procData.items():
                try:
                    if self.procList[pid]['pageCnt'] < procInfo['pageCnt']:
                        self.procList[pid]['pageCnt'] = procInfo['pageCnt']
                except:
                    self.procList[pid] = dict(self.init_procData)
                    self.procList[pid]['tids'] = {}
                    self.procList[pid]['pageCnt'] = procInfo['pageCnt']

                for tid, val in procInfo['tids'].items():
                    try:
                        self.procList[pid]['tids'][tid]
                    except:
                        self.procList[pid]['tids'][tid] = dict(self.init_threadData)
                        self.procList[pid]['tids'][tid]['comm'] = val['comm']

        if len(self.procList) == 0:
            SystemInfo.printError('No process profiled')
            sys.exit(0)

        # Merge file info into a global list #
        for fileData in self.intervalFileData:
            for fileName, fileInfo in fileData.items():
                try:
                    if self.fileList[fileName]['pageCnt'] < fileInfo['pageCnt']:
                        self.fileList[fileName]['pageCnt'] = fileInfo['pageCnt']
                except:
                    self.fileList[fileName] = dict(self.init_mapData)
                    self.fileList[fileName]['pageCnt'] = fileInfo['pageCnt']
                    self.fileList[fileName]['totalSize'] = fileInfo['totalSize']

        if len(self.fileList) == 0:
            SystemInfo.printError('No file profiled')
            sys.exit(0)

        # Print title #
        SystemInfo.printTitle()

        # Print proccess list #
        SystemInfo.pipePrint("[%s] [ Process : %d ] [ Keys: Foward/Back/Save/Quit ]" % \
        ('File Info', len(self.procList)))
        SystemInfo.pipePrint(twoLine)
        SystemInfo.pipePrint("{0:_^7}|{1:_^13}|{2:_^16}({3:_^7})".format("Pid", "MaxSize(KB)", "ThreadName", "Tid"))
        SystemInfo.pipePrint(twoLine)

        for pid, val in sorted(self.procList.items(), key=lambda e: int(e[1]['pageCnt']), reverse=True):
            printMsg = "{0:^7}|{1:12} ".format(pid, val['pageCnt'] * SystemInfo.pageSize / 1024)
            for tid, threadVal in sorted(val['tids'].items(), reverse=True):
                printMsg += "|{0:^16}({1:^7})".format(threadVal['comm'], tid)
                SystemInfo.pipePrint(printMsg)
                printMsg = "{0:^7}{1:^14}".format('', '')

        SystemInfo.pipePrint(oneLine + '\n\n\n')

        # Print file list #
        SystemInfo.pipePrint("[%s] [ File: %d ] [ Keys: Foward/Back/Save/Quit ]" % \
        ('File Info', len(self.fileList)))
        SystemInfo.pipePrint(twoLine)
        printMsg = "{0:_^12}|{1:_^10}|{2:_^5}|".format("Memory(KB)", "File(KB)", "%")
        if len(self.intervalFileData) > 1:
            for idx in range(1, len(self.intervalFileData)):
                printMsg += "{0:_^15}|".format(str(idx))
        printMsg += "\tPath"
        SystemInfo.pipePrint(printMsg)
                
        SystemInfo.pipePrint(twoLine)

        for fileName, val in sorted(self.fileList.items(), key=lambda e: int(e[1]['pageCnt']), reverse=True):
            memSize = self.intervalFileData[0][fileName]['pageCnt'] * SystemInfo.pageSize / 1024
            fileSize = ((val['totalSize'] + SystemInfo.pageSize - 1) / SystemInfo.pageSize) * SystemInfo.pageSize / 1024
            per = 0

            if fileSize != 0:
                per = int(int(memSize) / float(fileSize) * 100)

            printMsg = "{0:11} |{1:9} |{2:5}|".format(memSize, fileSize, per)
            if len(self.intervalFileData) > 1:
                for idx in range(1, len(self.intervalFileData)):
                    diffNew = 0
                    diffDel = 0
                    nowFileMap = self.intervalFileData[idx][fileName]['fileMap']
                    prevFileMap = self.intervalFileData[idx - 1][fileName]['fileMap']

                    if nowFileMap is None:
                        if prevFileMap is not None:
                            diffDel = self.intervalFileData[idx - 1][fileName]['pageCnt']
                    else:
                        if prevFileMap is None:
                            diffAdd = self.intervalFileData[idx - 1][fileName]['pageCnt']
                        else:
                            if len(nowFileMap) == len(prevFileMap):
                                for i in range(len(nowFileMap)):
                                    if nowFileMap[i] > prevFileMap[i]:
                                        diffNew += 1
                                    elif nowFileMap[i] < prevFileMap[i]:
                                        diffDel += 1

                    diffNew = diffNew * SystemInfo.pageSize / 1024
                    diffDel = diffDel * SystemInfo.pageSize / 1024
                    printMsg += "+%6d/-%6d|" % (diffNew, diffDel)

            printMsg += "\t%s" % fileName

            SystemInfo.pipePrint(printMsg)

        SystemInfo.pipePrint(oneLine + '\n\n\n')



    def makeReadaheadList(self):
        None



    def scanProcs(self):
        # scan comms include words in SystemInfo.showGroup #
        try:
            pids = os.listdir(self.procPath)
            for pid in pids:
                try: int(pid)
                except: continue

                # make path of tid #
                procPath = os.path.join(self.procPath, pid)
                taskPath = os.path.join(procPath, 'task')
                tids = os.listdir(taskPath)

                for tid in tids:
                    try: int(tid)
                    except: continue

                    # make path of comm #
                    threadPath = os.path.join(taskPath, tid)
                    commPath = os.path.join(threadPath, 'comm')

                    try:
                        fd = open(commPath, 'r')
                        comm = fd.readline()
                        comm = comm[0:len(comm) - 1]
                        fd.close()
                    except:
                        SystemInfo.printWarning('Fail to open %s' % (commPath))
                        continue

                    # save process info #
                    for val in SystemInfo.showGroup:
                        if comm.rfind(val) != -1 or tid == val:
                            # access procData #
                            try: self.procData[pid]
                            except: 
                                self.procData[pid] = dict(self.init_procData)
                                self.procData[pid]['tids'] = {}
                                self.procData[pid]['procMap'] = {}

                                # make or update mapInfo per process #
                                self.makeProcMapInfo(pid, threadPath + '/maps')

                            # access threadData #
                            try: self.procData[pid]['tids'][tid]
                            except:
                                self.procData[pid]['tids'][tid] = dict(self.init_threadData)
                                self.procData[pid]['tids'][tid]['comm'] = comm
        except:
            SystemInfo.printError('Fail to open %s' % self.procPath)



    def fillFileMaps(self):
        for fileName, val in self.fileData.items():
            if val['fileMap'] is not None:
                val['pageCnt'] = val['fileMap'].count(1)

        for pid, val in self.procData.items():
            for fileName, mapInfo in val['procMap'].items():
                if self.fileData[fileName]['fileMap'] is None or mapInfo is None:
                    continue

                # convert address and size to index in mapping table #
                offset = mapInfo['offset'] - self.fileData[fileName]['offset']
                offset = (offset + SystemInfo.pageSize - 1) / SystemInfo.pageSize
                size = (mapInfo['size'] + SystemInfo.pageSize - 1) / SystemInfo.pageSize

                mapInfo['fileMap'] = list(self.fileData[fileName]['fileMap'][offset:size])
                mapInfo['pageCnt'] = mapInfo['fileMap'].count(1)
                val['pageCnt'] += mapInfo['pageCnt']



    def makeProcMapInfo(self, pid, path):
        # open maps #
        try: fd = open(path, 'r')
        except:
            SystemInfo.printWarning('Fail to open %s' % (path))
            return

        # read maps #
        mapBuf = fd.readlines()

        # parse and merge lines in maps #
        for val in mapBuf:
            self.mergeMapLine(val, self.procData[pid]['procMap'])



    def mergeFileMapInfo(self):
        for idx, val in self.procData.items():
            for fileName, scope in val['procMap'].items():
                newOffset = scope['offset']
                newSize = scope['size']
                newEnd = newOffset + newSize

                # access fileData #
                try: 
                    savedOffset = self.fileData[fileName]['offset']
                    savedSize = self.fileData[fileName]['size']
                    savedEnd = savedOffset + savedSize

                    # bigger start address then saved one #
                    if savedOffset <= newOffset:
                        # merge bigger end address then saved one #
                        if savedEnd < newEnd:
                            self.fileData[fileName]['size'] += (newEnd - savedOffset - savedSize)
                        # ignore smaller end address then saved one #
                        else:
                            None
                    # smaller start address then saved one #
                    else:
                            if savedEnd >= newEnd:
                                self.fileData[fileName]['size'] += (savedOffset - newOffset)
                            else:
                                self.fileData[fileName]['size'] = newSize

                            self.fileData[fileName]['offset'] = newOffset
                except: 
                    self.fileData[fileName] = dict(self.init_mapData)
                    self.fileData[fileName]['offset'] = newOffset
                    self.fileData[fileName]['size'] = newSize



    def mergeMapLine(self, string, procMap):
        m = re.match('^(?P<startAddr>.\S+)-(?P<endAddr>.\S+) (?P<permission>.\S+) (?P<offset>.\S+) (?P<devid>.\S+) (?P<inode>.\S+)\s*(?P<binName>.+)', string)
        if m is not None:
            d = m.groupdict()

            fileName = d['binName']
            startAddr = int(d['startAddr'], 16)
            endAddr = int(d['endAddr'], 16)

            newOffset = int(d['offset'], 16)
            newSize = endAddr - startAddr
            newEnd = newOffset + newSize

            try: 
                savedOffset = procMap[fileName]['offset']
                savedSize = procMap[fileName]['size']
                savedEnd = savedOffset + savedSize

                # bigger start address then saved one #
                if savedOffset <= newOffset:
                    # merge bigger end address then saved one #
                    if savedEnd < newEnd:
                        procMap[fileName]['size'] += (newEnd - savedOffset - savedSize)
                    # ignore smaller end address then saved one #
                    else:
                        None
                # smaller start address then saved one #
                else:
                    if savedEnd >= newEnd:
                        procMap[fileName]['size'] += (savedOffset - newOffset)
                    else:
                        procMap[fileName]['size'] = newSize

                    procMap[fileName]['offset'] = newOffset
            except: 
                procMap[fileName] = dict(self.init_mapData)
                procMap[fileName]['offset'] = newOffset
                procMap[fileName]['size'] = newSize



    def getFilePageMaps(self):
        self.profSuccessCnt = 0
        self.profFailedCnt = 0

        for fileName, val in self.fileData.items():
            if SystemInfo.intervalEnable > 0:
                # use file descriptor already saved as possible #
                try:
                    val['fd'] = self.intervalFileData[len(self.intervalFileData) - 1][fileName]['fd']
                    val['totalSize'] = self.intervalFileData[len(self.intervalFileData) - 1][fileName]['totalSize']
                except: None

            if val['fd'] is None:
                try:
                    # open binary file to check page whether it is on memory or not #
                    fd = open(fileName, "r")
                    size = os.stat(fileName).st_size

                    val['fd'] = fd
                    val['totalSize'] = size

                    # check file size whether it is readable or not #
                    if size == 0:
                        raise
                except:
                    self.profFailedCnt += 1
                    if SystemInfo.showAll is True:
                        SystemInfo.printWarning('Fail to open %s' % fileName)
                    continue

            # prepare variables for mincore systemcall #
            fd = self.fileData[fileName]['fd'].fileno()
            offset = self.fileData[fileName]['offset']
            size = self.fileData[fileName]['size']

            # call mincore systemcall #
            pagemap = self.libguider.get_filePageMap(fd, offset, size)

            # save the array of ctype into list #
            if pagemap is not None:
                self.fileData[fileName]['fileMap'] = [pagemap[i] for i in range(size / SystemInfo.pageSize)]
                self.profSuccessCnt += 1

        if len(self.fileData) > 0:
            SystemInfo.printGood('Profiled a total of %d files' % self.profSuccessCnt)
        else:
            SystemInfo.printWarning('Profiled a total of %d files' % self.profSuccessCnt)

        if self.profFailedCnt > 0: 
            SystemInfo.printWarning('Failed to open a total of %d files' % self.profFailedCnt)





class SystemInfo:
    maxCore = 0
    pageSize = 4096
    blockSize = 512
    bufferSize = '40960'
    ttyRows = '50'
    ttyCols = '156'
    mountPath = None
    addr2linePath = None
    rootPath = None
    pipeForPrint = None
    fileForPrint = None
    inputFile = None
    outputFile = None
    printFile = None
    ttyEnable = True
    binEnable = False

    logSize = 0
    curLine = 0
    totalLine = 0
    dbgEventLine = 0

    graphEnable = False
    graphLabels= []
    bufferString = ''

    eventLogFile = None
    eventLogFD = None
    targetEvent = None

    showAll = False
    selectMenu = None
    intervalNow = 0

    tgidEnable = True
    irqEnable = False
    memEnable = False
    futexEnable = False
    pipeEnable = False
    depEnable = False
    sysEnable = False
    compareEnable = False
    functionEnable = False
    fileEnable = False
    threadEnable = False
    intervalEnable = 0

    repeatInterval = 0
    repeatCount = 0
    progressCnt = 0
    progressChar = {
            0: '|',
            1: '/',
            2: '-',
            3: '\\',
    }

    cmdList = {}
    preemptGroup = []
    showGroup = []
    syscallList = []

    # systemcall numbers about ARM architecture #
    sysWrite = '4'
    sysSelect = '142'
    sysPoll = '168'
    sysEpollwait = '252'
    sysRecv = '291'
    sysFutex = '240'



    def __init__(self):
        self.memData = {}

        self.memData['before'] = dict()
        self.memData['after'] = dict()

        eventLogFile = str(self.getMountPath()) + '/tracing/trace_marker'

        self.saveMeminfo()



    @staticmethod
    def stopHandler(signum, frame):
        if SystemInfo.fileEnable is True:
            FileInfo.condExit = True
        else:
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            SystemInfo.runRecordStopCmd()

        SystemInfo.printStatus('ready to save and analyze... [ STOP(ctrl + c) ]')



    @staticmethod
    def newHandler(signum, frame):
        if SystemInfo.fileEnable is True:
            SystemInfo.printStatus("Saved file usage successfully")
        else:
            if SystemInfo.compareEnable is False:
                SystemInfo.writeEvent("EVENT_MARK")
            else:
                SystemInfo.writeEvent("EVENT_RESTART")
                SystemInfo.printStatus('restart recording... [ STOP(ctrl + c) ]')



    @staticmethod
    def exitHandler(signum, frame):
        SystemInfo.printError('Terminated by user\n')
        sys.exit(0)



    @staticmethod
    def isRelocatableFile(path):
        if path.find('.so') == -1 and path.find('.ttf') == -1 and \
                path.find('.pak') == -1:
                    return False
        else:
            return True



    @staticmethod
    def exitHandlerForFSinfo(signum, frame):
        for dirnames in os.walk('/sys/class/block'):
            for subdirname in dirnames[1]:
                devPath = '/sys/class/block/' + subdirname + '/dev'
                sizePath = '/sys/class/block/' + subdirname + '/size'
                devFd = open(devPath, 'r')
                sizeFd = open(sizePath, 'r')
                dev = devFd.readline().rstrip()
                size = sizeFd.readline().rstrip()



    @staticmethod
    def timerHandler(signum, frame):
        raise



    @staticmethod
    def alarmHandler(signum, frame):
        if SystemInfo.pipeEnable is True:
            if SystemInfo.repeatCount > 0:
                SystemInfo.runRecordStopCmd()
                SystemInfo.repeatInterval = 5
                SystemInfo.repeatCount = 0
                signal.alarm(SystemInfo.repeatInterval)
            else:
                sys.exit(0)
        elif SystemInfo.repeatCount > 0:
            if SystemInfo.outputFile != None:
                output = SystemInfo.outputFile + str(SystemInfo.repeatCount)
                try:
                    shutil.copy(os.path.join(SystemInfo.mountPath + '../trace'), output)
                    SystemInfo.printInfo('trace data is saved to %s' % output)
                except:
                    SystemInfo.printWarning('Fail to save trace data to %s' % output)

                SystemInfo.repeatCount -= 1
                signal.alarm(SystemInfo.repeatInterval)
            else:
                SystemInfo.printError('Fail to save trace data because output file is not set')
                SystemInfo.runRecordStopCmd()
                sys.exit(0)
        else:
            SystemInfo.runRecordStopCmd()
            sys.exit(0)



    @staticmethod
    def saveDataAndExit(lines):
        # save trace data to file #
        try:
            if SystemInfo.outputFile != None:
                f = open(SystemInfo.outputFile, 'wt')
                f.writelines(lines)

                SystemInfo.runRecordStopFinalCmd()
                SystemInfo.printInfo('trace data is saved to %s' % (SystemInfo.outputFile))

                f.close()
                sys.exit(0)
        except IOError:
            SystemInfo.printError("Fail to write data to %s" % SystemInfo.outputFile)
            sys.exit(0)



    @staticmethod
    def writeCmd(path, val):
        try: fd = open(SystemInfo.mountPath + path, 'w')
        except:
            SystemInfo.printWarning("Fail to use %s event, please confirm kernel configuration" % path[0:path.find('/')])
            return -1
        try:
            fd.write(val)
            fd.close()
        except:
            SystemInfo.printWarning("Fail to apply command to %s" % path)
            return -2

        return 0



    @staticmethod
    def printProgress():
        SystemInfo.progressCnt += 1
        if SystemInfo.progressCnt % 1000 == 0:
            if SystemInfo.progressCnt == 4000: SystemInfo.progressCnt = 0
            sys.stdout.write('%3d' % (SystemInfo.curLine / float(SystemInfo.totalLine) * 100) + \
                    '% ' + SystemInfo.progressChar[SystemInfo.progressCnt / 1000] + '\b\b\b\b\b\b')
            sys.stdout.flush()
            gc.collect()



    @staticmethod
    def addPrint(string):
        SystemInfo.bufferString += string



    @staticmethod
    def clearPrint():
        del SystemInfo.bufferString
        SystemInfo.bufferString = ''



    @staticmethod
    def printTitle():
        if SystemInfo.printFile == None:
            os.system('clear')

        SystemInfo.pipePrint("[ g.u.i.d.e.r \tver.%s ]\n" % __version__)



    @staticmethod
    def writeEvent(message):
        if SystemInfo.eventLogFD == None:
            if SystemInfo.eventLogFile is None:
                SystemInfo.eventLogFile = str(SystemInfo.getMountPath()) + '/tracing/trace_marker'

            try: SystemInfo.eventLogFD = open(SystemInfo.eventLogFile, 'w')
            except: SystemInfo.printError("Fail to open %s for writing event\n" % SystemInfo.eventLogFD)

        if SystemInfo.eventLogFD != None:
            try:
                SystemInfo.eventLogFD.write(message)
                SystemInfo.printInfo('marked user-defined event')
                SystemInfo.eventLogFD.close()
                SystemInfo.eventLogFD = None
            except:
                SystemInfo.printError("Fail to write %s event\n" % (message))
        else:
            SystemInfo.printError("Fail to write %s event because there is no file descriptor\n" % (message))



    @staticmethod
    def pipePrint(line):
        if SystemInfo.pipeForPrint == None and SystemInfo.selectMenu == None and SystemInfo.printFile == None:
            try: SystemInfo.pipeForPrint = os.popen('less', 'w')
            except:
                SystemInfo.printError("less can not be found, use -o option to save output to file\n")
                sys.exit(0)

            if SystemInfo.ttyEnable == True:
                SystemInfo.setTtyCols(SystemInfo.ttyCols)

        if SystemInfo.pipeForPrint != None:
            try: SystemInfo.pipeForPrint.write(line + '\n')
            except:
                SystemInfo.printError("printing to pipe failed\n")
                SystemInfo.pipeForPrint = None

        if SystemInfo.printFile != None and SystemInfo.fileForPrint == None:
            if SystemInfo.isRecordMode() is False:
                SystemInfo.inputFile = SystemInfo.inputFile.replace('dat', 'out')
            else:
                SystemInfo.inputFile = SystemInfo.printFile + '/guider.out'

            SystemInfo.inputFile = SystemInfo.inputFile.replace('//', '/')

            try:
                SystemInfo.fileForPrint = open(SystemInfo.inputFile, 'w')

                # print output file name #
                if SystemInfo.printFile != None:
                    SystemInfo.printInfo("wrote output to %s successfully" % (SystemInfo.inputFile))
            except:
                SystemInfo.printError("Fail to open %s\n" % (SystemInfo.inputFile))
                sys.exit(0)

        if SystemInfo.fileForPrint != None:
            try: SystemInfo.fileForPrint.write(line + '\n')
            except:
                SystemInfo.printError("printing to file failed\n")
                SystemInfo.pipeForPrint = None
        else: print line



    @staticmethod
    def printWarning(line):
        print ConfigInfo.WARNING + '[Warning] ' + line + ConfigInfo.ENDC



    @staticmethod
    def printError(line):
        print ConfigInfo.FAIL + '[Error] ' + line + ConfigInfo.ENDC



    @staticmethod
    def printInfo(line):
        print ConfigInfo.BOLD + '[Info] ' + line + ConfigInfo.ENDC



    @staticmethod
    def printGood(line):
        print ConfigInfo.OKGREEN + '[Info] ' + line + ConfigInfo.ENDC



    @staticmethod
    def printUnderline(line):
        print ConfigInfo.UNDERLINE + line + ConfigInfo.ENDC



    @staticmethod
    def printStatus(line):
        print '\n' + ConfigInfo.SPECIAL + '[Step] ' + line + ConfigInfo.ENDC



    @staticmethod
    def parseAddOption():
        if len(sys.argv) <= 2: return

        for n in range(2, len(sys.argv)):
            if sys.argv[n][0] == '-':
                if sys.argv[n][1] == 'i':
                    if len(sys.argv[n].lstrip('-i')) == 0:
                        SystemInfo.intervalEnable = 1
                        continue
                    try: int(sys.argv[n].lstrip('-i'))
                    except:
                        SystemInfo.printError("wrong option value %s with -i option" % (sys.argv[n]))
                        if SystemInfo.isRecordMode() is True: SystemInfo.runRecordStopFinalCmd()
                        sys.exit(0)
                    if int(sys.argv[n].lstrip('-i')) >= 0:
                        SystemInfo.intervalEnable = int(sys.argv[n].lstrip('-i'))
                    else:
                        SystemInfo.printError("wrong option value %s with -i option, use integer value" % (sys.argv[n].lstrip('-i')))
                        if SystemInfo.isRecordMode() is True: SystemInfo.runRecordStopFinalCmd()
                        sys.exit(0)
                elif sys.argv[n][1] == 'o':
                    SystemInfo.printFile = str(sys.argv[n].lstrip('-o'))
                    SystemInfo.ttyEnable = False
                    if os.path.isdir(SystemInfo.printFile) == False:
                        SystemInfo.printError("wrong option value %s with -o option, use directory name" % (sys.argv[n].lstrip('-o')))
                        if SystemInfo.isRecordMode() is True: SystemInfo.runRecordStopFinalCmd()
                        sys.exit(0)
                elif sys.argv[n][1] == 'a':
                    SystemInfo.showAll = True
                elif sys.argv[n][1] == 'q':
                    SystemInfo.selectMenu = True
                    ConfigInfo.taskChainEnable = True
                elif sys.argv[n][1] == 'w':
                    SystemInfo.depEnable = True
                elif sys.argv[n][1] == 'p':
                    if SystemInfo.intervalEnable != 1:
                        SystemInfo.preemptGroup = sys.argv[n].lstrip('-p').split(',')
                    else: SystemInfo.printWarning("-i option is already enabled, -p option is disabled")
                elif sys.argv[n][1] == 'd':
                    options = sys.argv[n].lstrip('-d')
                    if options.rfind('t') != -1:
                        SystemInfo.ttyEnable = False
                        SystemInfo.printInfo("tty is default")
                elif sys.argv[n][1] == 't':
                    SystemInfo.sysEnable = True
                    SystemInfo.syscallList = sys.argv[n].lstrip('-t').split(',')
                    for val in SystemInfo.syscallList:
                        try: int(val)
                        except: SystemInfo.syscallList.remove(val)

                elif sys.argv[n][1] == 'g':
                    SystemInfo.showGroup = sys.argv[n].lstrip('-g').split(',')
                elif sys.argv[n][1] == 'e':
                    options = sys.argv[n].lstrip('-e')
                    if options.rfind('g') != -1:
                        SystemInfo.graphEnable = True
                        SystemInfo.printInfo("graph is made for resource usage")
                    if options.rfind('t') != -1:
                        SystemInfo.ttyEnable = True
                        SystemInfo.printInfo("tty is set")
                elif sys.argv[n][1] == 'g':
                    if SystemInfo.outputFile != None:
                        SystemInfo.printWarning("only specific threads are recorded")
                elif sys.argv[n][1] == 'f':
                    # Handle error about record option #
                    if SystemInfo.functionEnable is not False:
                        if SystemInfo.outputFile == None:
                            SystemInfo.printError("wrong option with -f, use also -s option for saving data")
                            if SystemInfo.isRecordMode() is True: SystemInfo.runRecordStopFinalCmd()
                            sys.exit(0)
                    else: SystemInfo.functionEnable = True

                    SystemInfo.targetEvent = sys.argv[n].lstrip('-f')
                    if len(SystemInfo.targetEvent) == 0:
                        SystemInfo.targetEvent = None
                elif sys.argv[n][1] == 'l':
                    #SystemInfo.addr2linePath = sys.argv[n].lstrip('-l')
                    SystemInfo.addr2linePath = sys.argv[n].lstrip('-l').split(',')
                elif sys.argv[n][1] == 'j':
                    SystemInfo.rootPath = sys.argv[n].lstrip('-j')
                elif sys.argv[n][1] == 'b':
                    None
                elif sys.argv[n][1] == 'c':
                    None
                elif sys.argv[n][1] == 's':
                    None
                elif sys.argv[n][1] == 'r':
                    None
                elif sys.argv[n][1] == 'm':
                    None
                else:
                    SystemInfo.printError("unrecognized option -%s" % (sys.argv[n][1]))
                    if SystemInfo.isRecordMode() is True: SystemInfo.runRecordStopFinalCmd()
                    sys.exit(0)
            else:
                SystemInfo.printError("wrong option %s" % (sys.argv[n]))
                if SystemInfo.isRecordMode() is True: SystemInfo.runRecordStopFinalCmd()
                sys.exit(0)

    @staticmethod
    def parseRecordOption():
        if len(sys.argv) <= 2: return

        for n in range(2, len(sys.argv)):
            if sys.argv[n][0] == '-':
                if sys.argv[n][1] == 'b':
                    try: int(sys.argv[n].lstrip('-b'))
                    except:
                        SystemInfo.printError("wrong option value %s with -b option" % (sys.argv[n]))
                        sys.exit(0)
                    if int(sys.argv[n].lstrip('-b')) > 0:
                        SystemInfo.bufferSize = str(sys.argv[n].lstrip('-b'))
                    else:
                        SystemInfo.printError("wrong option value %s with -b option" % (sys.argv[n].lstrip('-b')))
                        sys.exit(0)
                elif sys.argv[n][1] == 'f':
                    SystemInfo.functionEnable = True
                elif sys.argv[n][1] == 'e':
                    options = sys.argv[n].lstrip('-e')
                    if options.rfind('i') != -1:
                        SystemInfo.irqEnable = True
                        SystemInfo.printInfo("irq profile")
                    if options.rfind('m') != -1:
                        SystemInfo.memEnable = True
                        SystemInfo.printInfo("memory profile")
                    if options.rfind('p') != -1:
                        SystemInfo.pipeEnable = True
                        SystemInfo.printInfo("recording from pipe")
                    if options.rfind('f') != -1:
                        SystemInfo.futexEnable = True
                        SystemInfo.printInfo("futex profile")
                elif sys.argv[n][1] == 'g':
                    if SystemInfo.outputFile != None and SystemInfo.functionEnable is False:
                        SystemInfo.printWarning("only specific threads are recorded")
                    SystemInfo.showGroup = sys.argv[n].lstrip('-g').split(',')
                elif sys.argv[n][1] == 's':
                    if SystemInfo.isRecordMode() is False:
                        SystemInfo.printError("Fail to save data becuase this is not record mode")
                        sys.exit(0)
                    if len(SystemInfo.showGroup) > 0:
                        SystemInfo.printWarning("only specific threads are recorded")
                    SystemInfo.ttyEnable = False
                    SystemInfo.outputFile = str(sys.argv[n].lstrip('-s'))
                    if os.path.isdir(SystemInfo.outputFile) == True:
                        SystemInfo.outputFile = SystemInfo.outputFile + '/guider.dat'
                    elif os.path.isdir(SystemInfo.outputFile[:SystemInfo.outputFile.rfind('/')]) == True: None
                    else:
                        SystemInfo.printError("wrong option value %s with -s option" % (sys.argv[n].lstrip('-s')))
                        sys.exit(0)
                    SystemInfo.outputFile = SystemInfo.outputFile.replace('//', '/')
                elif sys.argv[n][1] == 'w':
                    SystemInfo.depEnable = True
                elif sys.argv[n][1] == 'c':
                    SystemInfo.compareEnable = True
                    SystemInfo.printInfo("compare mode")
                elif sys.argv[n][1] == 'm':
                    SystemInfo.fileEnable = True
                elif sys.argv[n][1] == 't':
                    SystemInfo.sysEnable = True
                    SystemInfo.syscallList = sys.argv[n].lstrip('-t').split(',')
                    for val in SystemInfo.syscallList:
                        try: int(val)
                        except: SystemInfo.syscallList.remove(val)
                elif sys.argv[n][1] == 'r':
                    repeatParams = sys.argv[n].lstrip('-r').split(',')
                    if len(repeatParams) != 2:
                        SystemInfo.printError("wrong option with -r, use -r[interval],[repeat]")
                        sys.exit(0)
                    elif int(repeatParams[0]) < 1 or int(repeatParams[1]) < 1:
                        SystemInfo.printError("wrong option with -r, use parameters bigger than 0")
                        sys.exit(0)
                    else:
                        SystemInfo.repeatInterval = int(repeatParams[0])
                        SystemInfo.repeatCount = int(repeatParams[1])
                elif sys.argv[n][1] == 'l':
                    None
                elif sys.argv[n][1] == 'j':
                    None
                elif sys.argv[n][1] == 'o':
                    None
                elif sys.argv[n][1] == 'i':
                    None
                elif sys.argv[n][1] == 'a':
                    None
                elif sys.argv[n][1] == 'd':
                    None
                elif sys.argv[n][1] == 'q':
                    None
                elif sys.argv[n][1] == 'g':
                    None
                elif sys.argv[n][1] == 'p':
                    None
                else:
                    SystemInfo.printError("wrong option -%s" % (sys.argv[n][1]))
                    sys.exit(0)
            else:
                SystemInfo.printError("wrong option %s" % (sys.argv[n]))
                sys.exit(0)



    @staticmethod
    def isRecordMode():
        if sys.argv[1] == 'record': return True
        else: return False




    @staticmethod
    def setRtPriority(pri):
        os.system('chrt -a -p %s %s' % (pri, os.getpid()))



    @staticmethod
    def setIdlePriority(pri):
        os.system('chrt -a -i -p %s %s' % (pri, os.getpid()))



    @staticmethod
    def setTtyCols(cols):
        os.system('stty cols %s' % (cols))



    @staticmethod
    def setTtyRows(rows):
        os.system('stty rows %s' % (rows))



    def saveMeminfo(self):
        f = open('/proc/meminfo', 'r')
        lines = f.readlines()

        if self.memData['before'] == {}: time = 'before'
        else: time = 'after'

        for l in lines:
            m = re.match('(?P<type>\S+):\s+(?P<size>[0-9]+)', l)
            if m is not None:
                d = m.groupdict()
                self.memData[time][d['type']] = d['size']
        f.close()



    def getMeminfo(self, data):
        return str(self.memData[time][d['type']])



    def getBufferSize(self):
        f = open(SystemInfo.mountPath + "../buffer_total_size_kb", 'r')
        lines = f.readlines()

        return int(lines[0])



    @staticmethod
    def copyPipeToFile(pipePath, filePath):
        try: pd = open(pipePath, 'r')
        except:
            SystemInfo.printError("Fail to open %s" % pipePath)
            sys.exit(0)

        try: fd = open(filePath, 'w') # use os.O_DIRECT | os.O_RDWR | os.O_TRUNC | os.O_CREAT #
        except:
            SystemInfo.printError("Fail to open %s" % filePath)
            sys.exit(0)

        while True:
            try:
                fd.write(pd.read(SystemInfo.pageSize))
                SystemInfo.repeatCount = 1
                SystemInfo.printProgress()
            except:
                pd.close()
                fd.close()
                return



    @staticmethod
    def getMountPath():
        f = open('/proc/mounts', 'r')
        lines = f.readlines()

        for l in lines:
            m = re.match('(?P<dev>\S+)\s+(?P<dir>\S+)\s+(?P<fs>\S+)', l)
            if m is not None:
                d = m.groupdict()
                if d['fs'] == 'debugfs':
                    f.close()
                    return d['dir']
        f.close()




    @staticmethod
    def clearTraceBuffer():
        SystemInfo.writeCmd("../trace", '')



    def initCmdList(self):
        self.cmdList["sched/sched_switch"] = True
        self.cmdList["sched/sched_process_wait"] = True
        self.cmdList["sched/sched_process_free"] = True
        self.cmdList["sched/sched_wakeup"] = SystemInfo.depEnable
        self.cmdList["irq"] = SystemInfo.irqEnable
        self.cmdList["signal"] = SystemInfo.depEnable
        self.cmdList["raw_syscalls/sys_enter"] = SystemInfo.depEnable
        self.cmdList["raw_syscalls/sys_exit"] = SystemInfo.depEnable
        self.cmdList["raw_syscalls"] = SystemInfo.sysEnable
        self.cmdList["kmem/mm_page_alloc"] = SystemInfo.memEnable
        self.cmdList["kmem/mm_page_free"] = SystemInfo.memEnable
        self.cmdList["kmem/kmalloc"] = SystemInfo.memEnable
        self.cmdList["kmem/kfree"] = SystemInfo.memEnable
        self.cmdList["filemap/mm_filemap_add_to_page_cache"] = False
        self.cmdList["filemap/mm_filemap_delete_from_page_cache"] = SystemInfo.memEnable
        self.cmdList["timer/hrtimer_start"] = False
        self.cmdList["block/block_bio_remap"] = True
        self.cmdList["block/block_rq_complete"] = True
        self.cmdList["writeback/writeback_dirty_page"] = True
        self.cmdList["writeback/wbc_writepage"] = True
        self.cmdList["vmscan/mm_vmscan_direct_reclaim_begin"] = True
        self.cmdList["vmscan/mm_vmscan_direct_reclaim_end"] = True
        self.cmdList["sched/sched_migrate_task"] = True
        self.cmdList["task"] = True
        self.cmdList["signal"] = True
        self.cmdList["power/machine_suspend"] = True
        self.cmdList["printk"] = True
        self.cmdList["power/cpu_idle"] = True
        self.cmdList["power/cpu_frequency"] = True
        self.cmdList["vmscan/mm_vmscan_wakeup_kswapd"] = False
        self.cmdList["vmscan/mm_vmscan_kswapd_sleep"] = False



    def runPeriodProc(self):
        pid = os.fork()

        if pid == 0:
            signal.signal(signal.SIGINT, 0)

            while True:
                time.sleep(0.0001)

            sys.exit(0)



    def runRecordStartCmd(self):
        cmd = self.getMountPath()
        if cmd == None:
            SystemInfo.mountPath = "/sys/kernel/debug"
            cmd = "mount -t debugfs nodev " + SystemInfo.mountPath + ";"
            os.system(cmd)
        else: SystemInfo.mountPath = str(cmd)

        SystemInfo.mountPath += "/tracing/events/"

        if os.path.isdir(SystemInfo.mountPath) == False:
            SystemInfo.printError("ftrace option in kernel is not enabled or guider needs root permission")
            sys.exit(0)

        self.clearTraceBuffer()
        SystemInfo.writeCmd("../buffer_size_kb", SystemInfo.bufferSize)
        self.initCmdList()

        SystemInfo.writeCmd('../trace_options', 'noirq-info')
        SystemInfo.writeCmd('../trace_options', 'noannotate')
        SystemInfo.writeCmd('../trace_options', 'print-tgid')

        if SystemInfo.functionEnable is not False:
            cmd = "common_pid != 0"

            if len(SystemInfo.showGroup) > 0:
                if len(SystemInfo.showGroup) > 1:
                    SystemInfo.printError("Only one tid is available to filter for funtion profile")
                    sys.exit(0)

                try:
                    int(SystemInfo.showGroup[0])
                    cmd = "common_pid == %s" % SystemInfo.showGroup[0]
                except:
                    if SystemInfo.showGroup[0].find('>') == -1 and SystemInfo.showGroup[0].find('<') == -1:
                        SystemInfo.printError("Wrong tid %s" % SystemInfo.showGroup[0])
                        sys.exit(0)
                    else:
                        if SystemInfo.showGroup[0].find('>') >= 0:
                            tid = SystemInfo.showGroup[0][0:SystemInfo.showGroup[0].find('>')]
                            try: int(tid)
                            except:
                                SystemInfo.printError("Wrong tid %s" % tid)
                                sys.exit(0)
                            cmd = "common_pid >= %s" % tid
                        elif SystemInfo.showGroup[0].find('<') >= 0:
                            tid = SystemInfo.showGroup[0][0:SystemInfo.showGroup[0].find('<')]
                            try: int(tid)
                            except:
                                SystemInfo.printError("Wrong tid %s" % tid)
                                sys.exit(0)
                            cmd = "common_pid <= %s" % tid

            SystemInfo.writeCmd('../trace_options', 'userstacktrace')
            SystemInfo.writeCmd('../trace_options', 'sym-userobj')
            SystemInfo.writeCmd('../trace_options', 'sym-addr')
            SystemInfo.writeCmd('../options/stacktrace', '1')

            self.cmdList["timer/hrtimer_start"] = True
            SystemInfo.writeCmd('timer/hrtimer_start/filter', cmd)
            SystemInfo.writeCmd('timer/hrtimer_start/enable', '1')

            self.cmdList["kmem/mm_page_alloc"] = True
            SystemInfo.writeCmd('kmem/mm_page_alloc/filter', cmd)
            SystemInfo.writeCmd('kmem/mm_page_alloc/enable', '1')

            self.cmdList["block/block_bio_remap"] = True
            cmd += " && (rwbs == R || rwbs == RA || rwbs == RM)"
            SystemInfo.writeCmd('block/block_bio_remap/filter', cmd)
            SystemInfo.writeCmd('block/block_bio_remap/enable', '1')

            self.cmdList["sched/sched_process_free"] = True
            SystemInfo.writeCmd('sched/sched_process_free/enable', '1')

            return

        if self.cmdList["sched/sched_switch"] is True:
            if len(SystemInfo.showGroup) > 0:
                cmd = "prev_pid == 0 || next_pid == 0 || "
                for comm in SystemInfo.showGroup:
                    cmd += "prev_comm == \"%s\" || next_comm == \"%s\" || " % (comm, comm)
                cmd = cmd[0:cmd.rfind("||")]
                SystemInfo.writeCmd('sched/sched_switch/filter', cmd)
            else: SystemInfo.writeCmd('sched/sched_switch/filter', '0')

            if SystemInfo.writeCmd('sched/sched_switch/enable', '1') < 0:
                SystemInfo.printError("sched option in kernel is not enabled")
                sys.exit(0)

        if self.cmdList["sched/sched_wakeup"] is True:
            SystemInfo.writeCmd('sched/sched_wakeup/enable', '1')

        if self.cmdList["irq"] is True:
            SystemInfo.writeCmd('irq/enable', '1')

        if self.cmdList["raw_syscalls/sys_enter"] is True:
            cmd = "(id == %s || id == %s || id == %s || id == %s || id == %s || id == %s)" \
            % (SystemInfo.sysWrite, SystemInfo.sysPoll, SystemInfo.sysEpollwait, SystemInfo.sysSelect, SystemInfo.sysRecv, SystemInfo.sysFutex)

            SystemInfo.writeCmd('raw_syscalls/sys_enter/filter', cmd)
            SystemInfo.writeCmd('raw_syscalls/sys_enter/enable', '1')
        elif SystemInfo.futexEnable is True:
            cmd = "(id == %s)" % (SystemInfo.sysFutex)
            SystemInfo.writeCmd('raw_syscalls/sys_enter/filter', cmd)
            SystemInfo.writeCmd('raw_syscalls/sys_enter/enable', '1')
            self.cmdList["raw_syscalls/sys_enter"] = True
        else:
            SystemInfo.writeCmd('raw_syscalls/sys_enter/filter', '0')
            SystemInfo.writeCmd('raw_syscalls/sys_enter/enable', '0')

        if self.cmdList["raw_syscalls/sys_exit"] is True:
            cmd = "((id == %s || id == %s || id == %s || id == %s || id == %s || id == %s) && ret > 0)" \
            % (SystemInfo.sysWrite, SystemInfo.sysPoll, SystemInfo.sysEpollwait, SystemInfo.sysSelect, SystemInfo.sysRecv, SystemInfo.sysFutex)

            SystemInfo.writeCmd('raw_syscalls/sys_exit/filter', cmd)
            SystemInfo.writeCmd('raw_syscalls/sys_exit/enable', '1')
        elif SystemInfo.futexEnable is True:
            cmd = "(id == %s  && ret == 0)" % (SystemInfo.sysFutex)
            SystemInfo.writeCmd('raw_syscalls/sys_exit/filter', cmd)
            SystemInfo.writeCmd('raw_syscalls/sys_exit/enable', '1')
            self.cmdList["raw_syscalls/sys_exit"] = True
        else:
            SystemInfo.writeCmd('raw_syscalls/sys_exit/filter', '0')
            SystemInfo.writeCmd('raw_syscalls/sys_exit/enable', '0')


        if self.cmdList["raw_syscalls"] is True:
            if len(SystemInfo.syscallList) > 0:
                cmd = "("
                for val in SystemInfo.syscallList:
                    cmd += " id == %s ||" % val
                    if SystemInfo.syscallList.index(val) == len(SystemInfo.syscallList) - 1:
                        cmd += " id == %s)" % val
                SystemInfo.writeCmd('raw_syscalls/filter', cmd)

            if SystemInfo.sysEnable is True and len(SystemInfo.syscallList) == 0:
                SystemInfo.writeCmd('raw_syscalls/filter', '0')
                SystemInfo.writeCmd('raw_syscalls/sys_enter/filter', '0')
                SystemInfo.writeCmd('raw_syscalls/sys_exit/filter', '0')

            SystemInfo.writeCmd('raw_syscalls/enable', '1')

        if self.cmdList["signal"] is True:
            if SystemInfo.depEnable == True:
                SystemInfo.writeCmd('signal/enable', '1')

        if self.cmdList["power/machine_suspend"] is True:
            SystemInfo.writeCmd('power/machine_suspend/enable', '1')

        if self.cmdList["kmem/mm_page_alloc"] is True:
            SystemInfo.writeCmd('kmem/mm_page_alloc/enable', '1')
        if self.cmdList["kmem/mm_page_free"] is True:
            SystemInfo.writeCmd('kmem/mm_page_free/enable', '1')
        if self.cmdList["kmem/kmalloc"] is True:
            SystemInfo.writeCmd('kmem/kmalloc/enable', '1')
        if self.cmdList["kmem/kfree"] is True:
            SystemInfo.writeCmd('kmem/kfree/enable', '1')
        if self.cmdList["filemap/mm_filemap_add_to_page_cache"] is True:
            SystemInfo.writeCmd('filemap/mm_filemap_add_to_page_cache/enable', '1')
        if self.cmdList["filemap/mm_filemap_delete_from_page_cache"] is True:
            SystemInfo.writeCmd('filemap/mm_filemap_delete_from_page_cache/enable', '1')

        if self.cmdList["block/block_bio_remap"] is True:
            cmd = "rwbs == R || rwbs == RA || rwbs == RM"
            SystemInfo.writeCmd('block/block_bio_remap/filter', cmd)
            SystemInfo.writeCmd('block/block_bio_remap/enable', '1')
        if self.cmdList["block/block_rq_complete"] is True:
            cmd = "rwbs == R || rwbs == RA || rwbs == RM"
            SystemInfo.writeCmd('block/block_rq_complete/filter', cmd)
            SystemInfo.writeCmd('block/block_rq_complete/enable', '1')

        if self.cmdList["writeback/writeback_dirty_page"] is True:
            SystemInfo.writeCmd('writeback/writeback_dirty_page/enable', '1')
        if self.cmdList["writeback/wbc_writepage"] is True:
            SystemInfo.writeCmd('writeback/wbc_writepage/enable', '1')

        if self.cmdList["power/cpu_idle"] is True:
            SystemInfo.writeCmd('power/cpu_idle/enable', '1')
        if self.cmdList["power/cpu_frequency"] is True:
            SystemInfo.writeCmd('power/cpu_frequency/enable', '1')

        if self.cmdList["vmscan/mm_vmscan_wakeup_kswapd"] is True:
            SystemInfo.writeCmd('vmscan/mm_vmscan_wakeup_kswapd/enable', '1')
        if self.cmdList["vmscan/mm_vmscan_kswapd_sleep"] is True:
            SystemInfo.writeCmd('vmscan/mm_vmscan_kswapd_sleep/enable', '1')

        if self.cmdList["vmscan/mm_vmscan_direct_reclaim_begin"] is True:
            SystemInfo.writeCmd('vmscan/mm_vmscan_direct_reclaim_begin/enable', '1')
        if self.cmdList["vmscan/mm_vmscan_direct_reclaim_end"] is True:
            SystemInfo.writeCmd('vmscan/mm_vmscan_direct_reclaim_end/enable', '1')

        if self.cmdList["task"] is True:
            SystemInfo.writeCmd('task/enable', '1')
        if self.cmdList["signal"] is True:
            SystemInfo.writeCmd('signal/enable', '1')
        if self.cmdList["sched/sched_migrate_task"] is True:
            SystemInfo.writeCmd('sched/sched_migrate_task/enable', '1')
        if self.cmdList["sched/sched_process_free"] is True:
            SystemInfo.writeCmd('sched/sched_process_free/enable', '1')
        if self.cmdList["sched/sched_process_wait"] is True:
            SystemInfo.writeCmd('sched/sched_process_wait/enable', '1')

        if self.cmdList["printk"] is True:
            SystemInfo.writeCmd('printk/enable', '1')

        return



    @staticmethod
    def runRecordStopCmd():
        for idx, val in SystemInfo.cmdList.items():
            if val is True or val is not False:
                SystemInfo.writeCmd(str(idx) + '/enable', '0')



    @staticmethod
    def runRecordStopFinalCmd():
        SystemInfo.writeCmd('../trace_options', 'nouserstacktrace')
        SystemInfo.writeCmd('../trace_options', 'nosym-userobj')
        SystemInfo.writeCmd('../trace_options', 'nosym-addr')
        SystemInfo.writeCmd('../options/stacktrace', '0')



    def printMemInfo(self):
        # print memInfo #
        SystemInfo.pipePrint('\n')
        SystemInfo.pipePrint('[Memory Info]')
        SystemInfo.pipePrint(twoLine)
        SystemInfo.pipePrint("[ TOTAL]  MemSize: %9s  SwapSiz: %9s" % (self.memData['before']['MemTotal'], self.memData['before']['SwapTotal']))
        SystemInfo.pipePrint("[BEFORE]  MemFree: %9s  Buffers: %9s  Cached: %9s  SwapFree: %9s" % \
        (self.memData['before']['MemFree'], self.memData['before']['Buffers'], self.memData['before']['Cached'], self.memData['before']['SwapFree']))
        SystemInfo.pipePrint("[ AFTER]  MemFree: %9s  Buffers: %9s  Cached: %9s  SwapFree: %9s" % \
        (self.memData['after']['MemFree'], self.memData['after']['Buffers'], self.memData['after']['Cached'], self.memData['after']['SwapFree']))
        SystemInfo.pipePrint("[ USAGE]  MemFree: %9s  Buffers: %9s  Cached: %9s  SwapFree: %9s" % \
        (int(self.memData['after']['MemFree']) - int(self.memData['before']['MemFree']), int(self.memData['after']['Buffers']) - \
        int(self.memData['before']['Buffers']), int(self.memData['after']['Cached']) - int(self.memData['before']['Cached']), \
        int(self.memData['after']['SwapFree']) - int(self.memData['before']['SwapFree'])))
        SystemInfo.pipePrint(twoLine)





class EventInfo:
    def __init__(self):
        self.eventData = {}



    def addEvent(self, time, event):
        # ramdom event #
        if len(event.split('_')) == 1:
            name = event
            ID = None
        # sequantial event #
        else:
            name = event.split('_')[0]
            ID = event.split('_')[1]

        try: self.eventData[name] # {'list': [ID, time, number], 'summary': [ID, cnt, avr, min, max, first, last]} #
        except: self.eventData[name] = {'list': [], 'summary': []}

        self.eventData[name]['list'].append([ID, time, sum(t[0] == ID for t in self.eventData[name]['list']) + 1])

        if sum(id[0] == ID for id in self.eventData[name]['summary']) == 0:
            self.eventData[name]['summary'].append([ID, 1, 0, 0, 0, time, 0])
        else:
            for n in self.eventData[name]['summary']:
                if n[0] == ID:
                    n[1] += 1;
                    n[6] = time;
                    break;



    def printEventInfo(self):
        if len(self.eventData) > 0:
            SystemInfo.pipePrint('\n' + twoLine)
            SystemInfo.pipePrint("%s# %s: %d\n" % ('', 'EVT', len(self.eventData)))
            self.printEvent(ti.startTime)
            SystemInfo.pipePrint(twoLine)



    def printEvent(self, startTime):
        for key,value in sorted(self.eventData.items(), key=lambda e: e[1], reverse=True):
            if self.eventData[key]['summary'][0][0] == None:
                SystemInfo.pipePrint("%10s: [total: %s]" % (key, len(self.eventData[key]['list'])))
            else:
                string = ''
                for n in sorted(self.eventData[key]['summary'], key=lambda slist: slist[0]):
                    string += '[%s: %d/%d/%d/%d/%.3f/%.3f] ' % (n[0], n[1], n[2], n[3], n[4], float(n[5]) - float(startTime), 0)
                SystemInfo.pipePrint("%10s: [total: %s] [subEvent: %s] %s" % \
                        (key, len(self.eventData[key]['list']), len(self.eventData[key]['summary']), string))




class ThreadInfo:
    def __init__(self, file):
        self.threadData = {}
        self.irqData = {}
        self.ioData = {}
        self.reclaimData = {}
        self.pageTable = {}
        self.kmemTable = {}
        self.intervalData = []
        self.depData = []
        self.sigData = []
        self.sysuserCallData = []
        self.lastJob = {}
        self.preemptData = []
        self.suspendData = []
        self.markData = []
        self.consoleData = []

        self.stopFlag = False
        self.totalTime = 0
        self.totalTimeOld = 0
        self.cxtSwitch = 0
        self.lastLog = None

        self.threadDataOld = {}
        self.irqDataOld = {}
        self.ioDataOld = {}
        self.reclaimDataOld = {}

        self.init_threadData = {'comm': '', 'usage': float(0), 'cpuRank': int(0), 'yield': int(0), 'cpuWait': float(0), 'pri': '0', \
                'ioWait': float(0), 'reqBlock': int(0), 'readBlock': int(0), 'ioRank': int(0), 'irq': float(0), 'reclaimWait': float(0), \
                'reclaimCnt': int(0), 'migrate': int(0), 'ptid': '0', 'new': ' ', 'die': ' ', 'preempted': int(0), 'preemption': int(0), \
                'start': float(0), 'stop': float(0), 'readCnt': int(0), 'readStart': float(0), 'maxRuntime': float(0), 'coreSchedCnt': int(0), \
                'dReclaimWait': float(0), 'dReclaimStart': float(0), 'dReclaimCnt': int(0), 'futexCnt': int(0), 'futexEnter': float(0), \
                'futexTotal': float(0), 'futexMax': float(0), 'lastStatus': 'N', 'offCnt': int(0), 'offTime': float(0), 'lastOff': float(0), \
                'nrPages': int(0), 'reclaimedPages': int(0), 'remainKmem': int(0), 'wasteKmem': int(0), 'kernelPages': int(0), 'childList': None, \
                'readBlockCnt': int(0), 'writeBlock': int(0), 'writeBlockCnt': int(0), 'cachePages': int(0), 'userPages': int(0), \
                'maxPreempted': float(0),'anonReclaimedPages': int(0), 'lastIdleStatus': int(0), 'longRunCore': int(-1), 'createdTime': float(0), \
                'waitStartAsParent': float(0), 'waitChild': float(0), 'waitParent': float(0), 'waitPid': int(0), 'tgid': '-'*5}
        self.init_irqData = {'name': '', 'usage': float(0), 'start': float(0), 'max': float(0), 'min': float(0), \
                'max_period': float(0), 'min_period': float(0), 'count': int(0)}
        self.init_intervalData = {'time': float(0), 'firstLogTime': float(0), 'cpuUsage': float(0), 'totalUsage': float(0), 'cpuPer': float(0), \
                'ioUsage': float(0), 'totalIoUsage': float(0), 'irqUsage': float(0), 'memUsage': float(0), 'totalMemUsage': float(0), \
                'kmemUsage': float(0), 'totalKmemUsage': float(0), 'coreSchedCnt': int(0), 'totalCoreSchedCnt': int(0), 'preempted': float(0), \
                'totalPreempted': float(0)}
        self.init_pageData = {'tid': '0', 'page': '0', 'flags': '0', 'type': '0', 'time': '0'}
        self.init_kmallocData = {'tid': '0', 'caller': '0', 'ptr': '0', 'req': int(0), 'alloc': int(0), 'time': '0', 'waste': int(0), 'core': int(0)}
        self.init_lastJob = {'job': '0', 'time': '0', 'tid': '0', 'prevWakeupTid': '0'}
        self.wakeupData = {'tid': '0', 'nr': '0', 'ret': '0', 'time': '0', 'args': '0', 'valid': int(0), 'from': '0', 'to': '0', 'corrupt': '0'}
        self.init_preemptData = {'usage': float(0), 'count': int(0), 'max': float(0)}
        self.init_syscallInfo = {'usage': float(0), 'last': float(0), 'count': int(0), 'max': float(0), 'min': float(0)}

        self.startTime = '0'
        self.finishTime = '0'
        self.lastTidPerCore = {}

        if SystemInfo.preemptGroup != None:
            for index in SystemInfo.preemptGroup:
                # preempted state [preemptBit, threadList, startTime, core, totalUsage] #
                self.preemptData.append([False, {}, float(0), 0, float(0)])

        try:
            f = open(file, 'r')
            lines = f.readlines()
        except IOError:
            SystemInfo.printError("Open %s" % file)
            sys.exit(0)

        SystemInfo.saveDataAndExit(lines)

        # start parsing logs #
        SystemInfo.printStatus('start analyzing... [ STOP(ctrl + c) ]')
        self.lastLog = lines[-1]
        SystemInfo.totalLine = len(lines)
        for idx, log in enumerate(lines):
            self.parse(log)
            if self.stopFlag == True: break

        # add comsumed time of jobs not finished yet to each threads #
        for idx, val in self.lastTidPerCore.items():
            self.threadData[val]['usage'] += (float(self.finishTime) - float(self.threadData[val]['start']))
                        # toDo: add time that had been blocking to read blocks from disk #

        f.close()

        self.totalTime = round(float(self.finishTime) - float(self.startTime), 7)

        # group filter #
        if len(SystemInfo.showGroup) > 0:
            for key,value in sorted(self.threadData.items(), key=lambda e: e[1], reverse=False):
                checkResult = False
                for val in SystemInfo.showGroup:
                    if value['comm'].rfind(val) != -1 or value['tgid'].rfind(val) != -1: checkResult = True
                if checkResult == False and key[0:2] != '0[':
                    try: del self.threadData[key]
                    except: None
        elif SystemInfo.sysEnable == True or len(SystemInfo.syscallList) > 0:
            SystemInfo.printWarning("-g option is not enabled, -t option is disabled")
            SystemInfo.sysEnable = False
            SystemInfo.syscallList = []

        # print thread usage #
        self.printUsage()

        # print resource usage of threads on timeline #
        if SystemInfo.intervalEnable > 0:
            self.printIntervalInfo()

        # print dependency about threads #
        if SystemInfo.depEnable == True:
            self.printDepInfo()

        # print kernel messages #
        self.printConsoleInfo()

        # print system call usage #
        self.printSyscallInfo()



    def makeTaskChain(self):
        if ConfigInfo.taskChainEnable != True: return

        while True:
            eventInput = raw_input('Input event name for taskchain: ')
            fd = ConfigInfo.openConfFile(eventInput)
            if fd != None: break

        ConfigInfo.writeConfData(fd, '[%s]\n' % (eventInput))
        threadInput = raw_input('Input tids of hot threads for taskchain (ex. 13,144,235): ')
        threadList = threadInput.split(',')
        ConfigInfo.writeConfData(fd, 'nr_tid=' + str(len(threadList)) + '\n')

        for index, t in enumerate(threadList):
            cmdline = ConfigInfo.readProcData(t, 'cmdline', 0)
            if cmdline == None: continue

            cmdline = cmdline[0:cmdline.find('\x00')]
            cmdline = cmdline[0:cmdline.rfind('/')]
            cmdline = cmdline.replace(' ','-')
            if len(cmdline) > 256: cmdline = cmdline[0:255]

            try: self.threadData[t]
            except:
                SystemInfo.printWarning("thread %s is not in profiled data" % t)
                continue

            ConfigInfo.writeConfData(fd, str(index) + '=' + ConfigInfo.readProcData(t, 'stat', 2).replace('\x00','-') + '+' + \
            cmdline + ' ' + str(self.threadData[t]['ioRank']) + ' ' + str(self.threadData[t]['reqBlock']) + ' ' + \
            str(self.threadData[t]['cpuRank']) + ' ' + str(self.threadData[t]['usage']) + '\n')

        SystemInfo.pipePrint("%s.tc is written successfully" % eventInput)



    def getRunTaskNum(self):
        return len(self.threadData)



    def printCreationTree(self, tid, loc):
        childList = self.threadData[tid]['childList']
        threadName = "%s(%s)" % (self.threadData[tid]['comm'], tid)

        if self.threadData[tid]['createdTime'] > 0:
            threadName += " <%2.3f>" % (self.threadData[tid]['createdTime'] - float(self.startTime))
        if self.threadData[tid]['childList'] is not None:
            threadName += " |%d|" % (len(self.threadData[tid]['childList']))
        if self.threadData[tid]['waitChild'] > 0:
            threadName += " {%1.3f}" % (self.threadData[tid]['waitChild'])
        if self.threadData[tid]['waitParent'] > 0:
            threadName += " [%1.3f]" % (self.threadData[tid]['waitParent'])

        newLoc = loc + len(threadName) / 2 + 2

        if self.threadData[tid]['die'] == ' ':
            life = '+ '
        else:
            life = '- '

        SystemInfo.pipePrint(' ' * loc + life + threadName)

        if childList != None:
            for thread in childList:
                self.printCreationTree(thread, newLoc)



    def printUsage(self):
        # print title #
        SystemInfo.printTitle()

        # print menu #
        SystemInfo.pipePrint("[%s] [ %s: %0.3f ] [ Running: %d ] [ CtxSwc: %d ] [ LogSize: %d KB ] [ Keys: Foward/Back/Save/Quit ] [ Unit: Sec/MB ]" % \
        ('Thread Info', 'Elapsed time', round(float(self.totalTime), 7), self.getRunTaskNum(), self.cxtSwitch, SystemInfo.logSize / 1024))
        SystemInfo.pipePrint(twoLine)
        SystemInfo.pipePrint("{0:_^32}|{1:_^35}|{2:_^22}|{3:_^26}|{4:_^34}|".\
                format("Thread Info", "CPU Info", "SCHED Info", "BLOCK Info", "MEM Info"))
        SystemInfo.pipePrint("{0:^32}|{1:^35}|{2:^22}|{3:^26}|{4:^34}|".\
                format("", "", "", "", "", ""))
        SystemInfo.pipePrint("%16s(%5s/%5s)|%2s|%5s(%5s)|%5s(%5s)|%3s|%5s|%5s|%5s|%5s|%4s|%5s(%3s/%5s)|%4s(%3s)|%4s(%3s|%3s|%3s)|%3s|%3s|%4s(%2s)|" % \
        ('Name', 'Tid', 'Pid', 'LF', 'Usage', '%', 'Delay', 'Max', 'Pri', ' IRQ ', 'Yld', ' Lose', 'Steal', 'Mig', 'Read', 'MB', 'Cnt', 'WCnt', 'MB', \
        'Sum', 'Usr', 'Buf', 'Ker', 'Rcl', 'Wst', 'DRcl', 'Nr'))
        SystemInfo.pipePrint(twoLine)

        # initialize swapper thread per core #
        for n in range(0, SystemInfo.maxCore + 1):
            try: self.threadData['0[' + str(n) + ']']
            except:
                self.threadData['0[' + str(n) + ']'] = dict(self.init_threadData)
                self.threadData['0[' + str(n) + ']']['comm'] = 'swapper/' + str(n)
                self.threadData['0[' + str(n) + ']']['usage'] = 0

        # sort by size of io usage and convert read blocks to MB size #
        count = 0
        for key,value in sorted(self.threadData.items(), key=lambda e: e[1]['readBlock'], reverse=True):
            value['ioRank'] = count + 1
            if value['readBlock'] > 0:
                value['readBlock'] =  value['readBlock'] * SystemInfo.blockSize / 1024 / 1024
                count += 1
            if value['writeBlock'] > 0:
                value['writeBlock'] =  value['writeBlock'] * SystemInfo.pageSize / 1024 / 1024

       # print total information after sorting by time of cpu usage #
        count = 0
        SystemInfo.clearPrint()
        for key,value in sorted(self.threadData.items(), key=lambda e: e[1]['comm'], reverse=False):
            if key[0:2] == '0[':
                # change the name of swapper thread to CORE #
                value['comm'] = value['comm'].replace("swapper", "CORE");

                # modify idle time if this core is not woke up #
                if value['usage'] == 0 and value['coreSchedCnt'] == 0:
                    value['usage'] = self.totalTime

                # calculate total core usage percentage #
                usagePercent = 100 - (round(float(value['usage']) / float(self.totalTime), 7) * 100)
                if value['lastOff'] > 0:
                    value['offTime'] += float(self.finishTime) - value['lastOff']
                SystemInfo.addPrint(\
                    "%16s(%5s/%5s)|%s%s|%5.2f(%5s)|%5.2f(%5.2f)|%3s|%5.2f|%5d|%5s|%5s|%4s|%5.2f(%3d/%5d)|%4s(%3s)|%4s(%3s|%3s|%3s)|%3s|%3s|%4.2f(%2d)|\n" \
                    % (value['comm'], '0', '0', '-', '-', \
                    self.totalTime - value['usage'], str(round(float(usagePercent), 1)), round(float(value['offTime']), 7), 0, 0, value['irq'], \
                    value['offCnt'], '-', '-', '-', \
                    value['ioWait'], value['readBlock'], value['readBlockCnt'], value['writeBlockCnt'], value['writeBlock'], \
                    (value['nrPages'] * 4 / 1024) + (value['remainKmem'] / 1024 / 1024), \
                    value['userPages'] * 4 / 1024, value['cachePages'] * 4 / 1024, value['kernelPages'] * 4 / 1024 + (value['remainKmem'] / 1024 / 1024), \
                    (value['reclaimedPages'] * 4 / 1024), value['wasteKmem'] / 1024 / 1024, \
                    value['dReclaimWait'], value['dReclaimCnt']))
                count += 1
            else:
                # convert priority #
                prio = int(value['pri']) - 120
                if prio >= -20: value['pri'] = str(prio)
                else: value['pri'] = 'R%2s' % abs(prio + 21)

        SystemInfo.pipePrint("%s# %s: %d\n" % ('', 'CPU', count))
        SystemInfo.pipePrint(SystemInfo.bufferString)
        SystemInfo.pipePrint(oneLine)

        # compare thread information after sorting by time of cpu usage #
        if self.threadDataOld != {}:
            self.compareThreadData()

        # print thread information after sorting by time of cpu usage #
        count = 0
        SystemInfo.clearPrint()
        for key,value in sorted(self.threadData.items(), key=lambda e: e[1]['usage'], reverse=True):
            if key[0:2] == '0[': continue
            usagePercent = round(float(value['usage']) / float(self.totalTime), 7) * 100
            if round(float(usagePercent), 1) < 1 and SystemInfo.showAll == False: break
            else:
                value['cpuRank'] = count + 1
                count += 1
            SystemInfo.addPrint(\
                    "%16s(%5s/%5s)|%s%s|%5.2f(%5s)|%5.2f(%5.2f)|%3s|%5.2f|%5d|%5s|%5s|%4s|%5.2f(%3d/%5d)|%4s(%3s)|%4d(%3d|%3d|%3d)|%3d|%3d|%4.2f(%2d)|\n" % \
                    (value['comm'], key, value['tgid'], value['new'], value['die'], value['usage'], str(round(float(usagePercent), 1)), \
                    value['cpuWait'], value['maxPreempted'], value['pri'], value['irq'], \
                    value['yield'], value['preempted'], value['preemption'], value['migrate'], \
                    value['ioWait'], value['readBlock'], value['readBlockCnt'], value['writeBlockCnt'], value['writeBlock'], \
                    (value['nrPages'] * 4 / 1024) + (value['remainKmem'] / 1024 / 1024), \
                    value['userPages'] * 4 / 1024, value['cachePages'] * 4 / 1024, value['kernelPages'] * 4 / 1024 + (value['remainKmem'] / 1024 / 1024), \
                    value['reclaimedPages'] * 4 / 1024, value['wasteKmem'] / 1024 / 1024, \
                    value['dReclaimWait'], value['dReclaimCnt']))

        SystemInfo.pipePrint("%s# %s: %d\n" % ('', 'Hot', count))
        SystemInfo.pipePrint(SystemInfo.bufferString)
        SystemInfo.pipePrint(oneLine)

        # print thread preempted information after sorting by time of cpu usage #
        for val in SystemInfo.preemptGroup:
            index = SystemInfo.preemptGroup.index(val)
            count = 0

            tid = SystemInfo.preemptGroup[index]
            try: self.threadData[tid]
            except:
                SystemInfo.printError("Fail to find %s task" % tid)
                sys.exit(0)

            SystemInfo.clearPrint()
            for key, value in sorted(self.preemptData[index][1].items(), key=lambda e: e[1]['usage'], reverse=True):
                count += 1
                if float(self.preemptData[index][4]) == 0: break
                SystemInfo.addPrint("%16s(%5s/%5s)|%6.3f(%5s)\n" \
                % (self.threadData[key]['comm'], key, '0', value['usage'], \
                str(round(float(value['usage']) / float(self.preemptData[index][4]) * 100, 1))))
            SystemInfo.pipePrint("%s# %s: Tid(%s) / Comm(%s) / Total(%6.3f) / Threads(%d)\n" % \
                    ('', 'PRT', tid, self.threadData[tid]['comm'], self.preemptData[index][4], count))
            SystemInfo.pipePrint(SystemInfo.bufferString)
            SystemInfo.pipePrint(oneLine)

        # print new thread information after sorting by new thread flags #
        count = 0
        SystemInfo.clearPrint()
        for key,value in sorted(self.threadData.items(), key=lambda e: e[1]['new'], reverse=True):
            if value['new'] == ' ' or SystemInfo.selectMenu != None: break
            count += 1
            if SystemInfo.showAll == True:
                SystemInfo.addPrint(\
                "%16s(%5s/%5s)|%s%s|%5.2f(%5s)|%5.2f(%5.2f)|%3s|%5.2f|%5d|%5s|%5s|%4s|%5.2f(%3d/%5d)|%4s(%3s)|%4d(%3d|%3d|%3d)|%3d|%3d|%4.2f(%2d)|\n" % \
                (value['comm'], key, value['ptid'], value['new'], value['die'], value['usage'], str(round(float(usagePercent), 1)), \
                value['cpuWait'], value['maxPreempted'], value['pri'], value['irq'], \
                value['yield'], value['preempted'], value['preemption'], value['migrate'], \
                value['ioWait'], value['readBlock'], value['readBlockCnt'], value['writeBlockCnt'], value['writeBlock'], \
                (value['nrPages'] * 4 / 1024) + (value['remainKmem'] / 1024 / 1024), \
                value['userPages'] * 4 / 1024, value['cachePages'] * 4 / 1024, value['kernelPages'] * 4 / 1024 + (value['remainKmem'] / 1024 / 1024), \
                value['reclaimedPages'] * 4 / 1024, value['wasteKmem'] / 1024 / 1024, \
                value['dReclaimWait'], value['dReclaimCnt']))
        if count > 0:
            SystemInfo.pipePrint("%s# %s: %d\n" % ('', 'New', count))
            SystemInfo.pipePrint(SystemInfo.bufferString)
            SystemInfo.pipePrint(oneLine)

        # print die thread information after sorting by die thread flags #
        count = 0
        SystemInfo.clearPrint()
        for key,value in sorted(self.threadData.items(), key=lambda e: e[1]['die'], reverse=True):
            if value['die'] == ' ' or SystemInfo.selectMenu != None: break
            count += 1
            usagePercent = round(float(value['usage']) / float(self.totalTime), 7) * 100
            if SystemInfo.showAll == True:
                SystemInfo.addPrint(\
                "%16s(%5s/%5s)|%s%s|%5.2f(%5s)|%5.2f(%5.2f)|%3s|%5.2f|%5d|%5s|%5s|%4s|%5.2f(%3d/%5d)|%4s(%3s)|%4d(%3d|%3d|%3d)|%3d|%3d|%4.2f(%2d)|\n" % \
                (value['comm'], key, value['ptid'], value['new'], value['die'], value['usage'], str(round(float(usagePercent), 1)), \
                value['cpuWait'], value['maxPreempted'], value['pri'], value['irq'], \
                value['yield'], value['preempted'], value['preemption'], value['migrate'], \
                value['ioWait'], value['readBlock'], value['readBlockCnt'], value['writeBlockCnt'], value['writeBlock'], \
                (value['nrPages'] * 4 / 1024) + (value['remainKmem'] / 1024 / 1024), \
                value['userPages'] * 4 / 1024, value['cachePages'] * 4 / 1024, value['kernelPages'] * 4 / 1024 + (value['remainKmem'] / 1024 / 1024), \
                value['reclaimedPages'] * 4 / 1024, value['wasteKmem'] / 1024 / 1024, \
                value['dReclaimWait'], value['dReclaimCnt']))
        if count > 0:
            SystemInfo.pipePrint("%s# %s: %d\n" % ('', 'Die', count))
            SystemInfo.pipePrint(SystemInfo.bufferString)
            SystemInfo.pipePrint(oneLine)

        # print thread tree by creation #
        if SystemInfo.showAll == True and len(SystemInfo.showGroup) == 0:
            SystemInfo.clearPrint()
            SystemInfo.pipePrint('\n' + '[Creation Info] [Alive: +] [Die: -] [CreatedTime: <>] [ChildCount: ||] [WaitTimeForChilds: {}] [WaitTimeOfParent: ()]')
            SystemInfo.pipePrint(twoLine)

            for key,value in sorted(self.threadData.items(), key=lambda e: e[1]['waitChild'], reverse=True):
                # print tree from root threads #
                if value['childList'] is not None and value['new'] is ' ':
                    self.printCreationTree(key, 0)
                elif value['childList'] is None:
                    break
            SystemInfo.pipePrint(oneLine)

        # print signal traffic #
        if SystemInfo.showAll == True and len(SystemInfo.showGroup) == 0:
            SystemInfo.clearPrint()
            SystemInfo.pipePrint('\n' + '[Signal Info]')
            SystemInfo.pipePrint(twoLine)
            SystemInfo.pipePrint("%4s\t %8s\t %16s(%5s) \t%9s->\t %16s(%5s)" % \
                    ('TYPE', 'TIME', 'SENDER', 'TID', 'SIGNAL', 'RECVER', 'TID'))
            SystemInfo.pipePrint(twoLine)

            for val in self.sigData:
                try: ConfigInfo.sigList[int(val[6])]
                except: continue

                if val[0] == 'SEND':
                    SystemInfo.pipePrint("%4s\t %3.6f\t %16s(%6s) \t%9s->\t %16s(%5s)" % \
                            (val[0], val[1], val[2], val[3], ConfigInfo.sigList[int(val[6])], val[4], val[5]))
                elif val[0] == 'RECV':
                    SystemInfo.pipePrint("%4s\t %3.6f\t %16s(%6s) \t%9s->\t %16s(%5s)" % \
                            (val[0], val[1], '', '', ConfigInfo.sigList[int(val[6])], val[4], val[5]))
            SystemInfo.pipePrint(oneLine)

        # print interrupt information #
        if len(self.irqData) > 0:
            totalCnt = int(0)
            totalUsage = float(0)

            SystemInfo.pipePrint('\n' + '[IRQ Info]')
            SystemInfo.pipePrint(twoLine)
            SystemInfo.pipePrint("%16s(%16s): \t%6s\t\t%8s\t%8s\t%8s\t%8s\t%8s" % \
                    ("IRQ", "Name", "Count", "Usage", "ProcMax", "ProcMin", "InterMax", "InterMin"))
            SystemInfo.pipePrint(twoLine)

            SystemInfo.clearPrint()
            for key in sorted(self.irqData.keys()):
                totalCnt += self.irqData[key]['count']
                totalUsage += self.irqData[key]['usage']
                SystemInfo.addPrint("%16s(%16s): \t%6d\t\t%.6f\t%0.6f\t%0.6f\t%0.6f\t%0.6f\n" % \
                (key, self.irqData[key]['name'], self.irqData[key]['count'], self.irqData[key]['usage'], self.irqData[key]['max'], \
                self.irqData[key]['min'], self.irqData[key]['max_period'], self.irqData[key]['min_period']))

            SystemInfo.pipePrint("%s# IRQ(%d) / Total(%6.3f) / Cnt(%d)\n" % ('', len(self.irqData), totalUsage, totalCnt))
            SystemInfo.pipePrint(SystemInfo.bufferString)
            SystemInfo.pipePrint(oneLine)

        # set option for making graph #
        if SystemInfo.graphEnable == True and SystemInfo.intervalEnable > 0:
            SystemInfo.printInfo("graph is enabled")
            os.environ['DISPLAY'] = 'localhost:0'
            rc('legend', fontsize=5)
            rcParams.update({'font.size': 8})
        else: SystemInfo.graphEnable = False



    def printDepInfo(self):
        SystemInfo.clearPrint()
        SystemInfo.pipePrint('\n' + '[Dependency Info]')
        SystemInfo.pipePrint(twoLine)
        SystemInfo.pipePrint("\t%5s/%4s \t%16s(%4s) -> %16s(%4s) \t%5s" % ("Total", "Inter", "From", "Tid", "To", "Tid", "Event"))
        SystemInfo.pipePrint(twoLine)
        SystemInfo.pipePrint("%s# %s: %d\n" % ('', 'Dep', len(self.depData)))

        for icount in range(0, len(self.depData)):
            SystemInfo.addPrint(self.depData[icount] + '\n')

        SystemInfo.pipePrint(SystemInfo.bufferString)
        SystemInfo.pipePrint(oneLine)



    def printSyscallInfo(self):
        count = 0
        SystemInfo.clearPrint()
        if self.sysuserCallData != []:
            if len(SystemInfo.showGroup) > 0:
                SystemInfo.pipePrint('\n' + '[Syscall Info]')
                SystemInfo.pipePrint(twoLine)
                SystemInfo.pipePrint("%16s(%4s)\t%7s\t\t%6s\t\t%6s\t\t%6s\t\t%6s\t\t%6s" % \
                        ("Name", "Tid", "SysId", "Usage", "Count", "Min", "Max", "Avg"))
                SystemInfo.pipePrint(twoLine)

                for key,value in sorted(self.threadData.items(), key=lambda e: e[1]['comm']):
                    if key[0:2] == '0[': continue
                    SystemInfo.pipePrint("%16s(%4s)" % (self.threadData[key]['comm'], key))
                    try:
                        for sysId,val in sorted(self.threadData[key]['syscallInfo'].items(), key=lambda e: e[1]['usage'], reverse=True):
                            if val['count'] > 0:
                                val['average'] = val['usage'] / val['count']
                                SystemInfo.pipePrint("\t%27s\t\t%6.3f\t\t%6d\t\t%6.3f\t\t%6.3f\t\t%6.3f\n" % \
                                (sysId, val['usage'], val['count'], val['min'], val['max'], val['average']))
                    except: continue
                SystemInfo.pipePrint(SystemInfo.bufferString)
                SystemInfo.pipePrint(oneLine)

            SystemInfo.clearPrint()
            if SystemInfo.showAll == True:
                SystemInfo.pipePrint('\n' + twoLine)
                SystemInfo.pipePrint("%16s(%4s)\t%8s\t%5s\t%6s\t%4s\t%s" % ("Name", "Tid", "Time", "Type", "NR", "Core", "Value"))
                SystemInfo.pipePrint(twoLine)

                for icount in range(0, len(self.sysuserCallData)):
                    try:
                        SystemInfo.addPrint("%16s(%4s)\t%6.6f\t%5s\t%6s\t%4s\t%s\n" % \
                        (self.threadData[self.sysuserCallData[icount][2]]['comm'], self.sysuserCallData[icount][2], \
                        round(float(self.sysuserCallData[icount][1]) - float(self.startTime), 7), self.sysuserCallData[icount][0], \
                        self.sysuserCallData[icount][4], self.sysuserCallData[icount][3], self.sysuserCallData[icount][5]))
                        if self.sysuserCallData[icount][0] == 'enter':
                            count += 1
                    except: None
                SystemInfo.pipePrint("%s# %s: %d\n" % ('', 'Sys', count))
                SystemInfo.pipePrint(SystemInfo.bufferString)
                SystemInfo.pipePrint(oneLine)



    def printConsoleInfo(self):
        if len(self.consoleData) > 0 and SystemInfo.showAll == True:
            SystemInfo.pipePrint('\n' + '[Message Info]')
            SystemInfo.pipePrint(twoLine)
            SystemInfo.pipePrint("%16s %5s %4s %10s %30s" % ('Name', 'Tid', 'Core', 'Time', 'Console message'))
            SystemInfo.pipePrint(twoLine)
            for msg in self.consoleData:
                try:
                    SystemInfo.pipePrint("%16s %5s %4s %10.3f %s" % \
                            (self.threadData[msg[0]]['comm'], msg[0], msg[1], round(float(msg[2]) - float(self.startTime), 7), msg[3]))
                except: continue
            SystemInfo.pipePrint(twoLine)



    def printIntervalInfo(self):
        SystemInfo.pipePrint('\n' + '[Interval Info]')
        SystemInfo.pipePrint(twoLine)

        # Total timeline #
        timeLine = ''
        for icount in range(1, int(float(self.totalTime) / SystemInfo.intervalEnable) + 2):
            checkEvent = ' '
            cnt = icount - 1

            # check suspend event #
            for val in self.suspendData:
                if float(self.startTime) + cnt * SystemInfo.intervalEnable < float(val[0]) < \
                        float(self.startTime) + ((cnt + 1) * SystemInfo.intervalEnable):
                    if val[1] == 'S': checkEvent = '!'
                    else: checkEvent = '>'

            # check mark event #
            for val in self.markData:
                if float(self.startTime) + cnt * SystemInfo.intervalEnable < float(val) < \
                        float(self.startTime) + ((cnt + 1) * SystemInfo.intervalEnable):
                    checkEvent = 'v'

            # print timeline #
            if icount * SystemInfo.intervalEnable < float(self.totalTime):
                timeLine += '%s%2d ' % (checkEvent, icount * SystemInfo.intervalEnable)
            else:
                timeLine += '%s%.2f ' % (checkEvent, self.totalTime)

        SystemInfo.pipePrint("%16s(%5s/%5s): %s" % ('Name', 'Tid', 'Pid', timeLine))
        SystemInfo.pipePrint(twoLine)
        SystemInfo.clearPrint()

        # total CPU in timeline #
        for key,value in sorted(self.threadData.items(), key=lambda e: e[1]['comm'], reverse=False):
            if key[0:2] == '0[':
                icount = 0
                timeLine = ''
                for icount in range(0, int(float(self.totalTime) / SystemInfo.intervalEnable) + 1):
                    try: self.intervalData[icount][key]
                    except:
                        timeLine += '%3s ' % '0'
                        continue

                    timeLine += '%3d ' % (100 - self.intervalData[icount][key]['cpuPer'])
                SystemInfo.addPrint("%16s(%5s/%5s): " % (value['comm'], '0', value['tgid']) + timeLine + '\n')

                if SystemInfo.graphEnable == True:
                    subplot(2,1,1)
                    timeLineData = [int(n) for n in timeLine.split()]
                    range(SystemInfo.intervalEnable, (len(timeLineData)+1)*SystemInfo.intervalEnable, SystemInfo.intervalEnable)
                    plot(range(SystemInfo.intervalEnable, (len(timeLineData)+1)*SystemInfo.intervalEnable, SystemInfo.intervalEnable), timeLineData, '.-')
                    SystemInfo.graphLabels.append(value['comm'])

        if SystemInfo.graphEnable == True:
            title('Core Usage')
            ylabel('Percentage(%)', fontsize=10)
            legend(SystemInfo.graphLabels, bbox_to_anchor=(1.135, 1.02))
            del SystemInfo.graphLabels[:]

        # total MEM in timeline #
        icount = 0
        timeLine = ''
        for icount in range(0, int(float(self.totalTime) / SystemInfo.intervalEnable) + 1):
            try: timeLine += '%3d ' % ((self.intervalData[icount]['toTal']['totalMem'] * 4 / 1024) + \
                    (self.intervalData[icount]['toTal']['totalKmem'] / 1024 / 1024))
            except: timeLine += '%3d ' % (0)
        SystemInfo.addPrint("\n%16s(%5s/%5s): " % ('MEM', '0', '-----') + timeLine + '\n')

        # total BLOCK_READ in timeline #
        icount = 0
        timeLine = ''
        for icount in range(0, int(float(self.totalTime) / SystemInfo.intervalEnable) + 1):
            try: timeLine += '%3d ' % (self.intervalData[icount]['toTal']['totalIo'] * SystemInfo.blockSize / 1024 / 1024)
            except: timeLine += '%3d ' % (0)
        SystemInfo.addPrint("\n%16s(%5s/%5s): " % ('BLK_RD', '0', '-----') + timeLine + '\n')

        SystemInfo.pipePrint("%s# %s\n" % ('', 'Total(%/MB)'))
        SystemInfo.pipePrint(SystemInfo.bufferString)
        SystemInfo.pipePrint(oneLine)
        SystemInfo.clearPrint()
        tcount = 0;

        # CPU timeline #
        for key,value in sorted(self.threadData.items(), key=lambda e: e[1]['usage'], reverse=True):
            if key[0:2] != '0[':
                icount = 0
                timeLine = ''
                for icount in range(0, int(float(self.totalTime) / SystemInfo.intervalEnable) + 1):
                    try: self.intervalData[icount][key]
                    except:
                        timeLine += '%3d ' % 0
                        continue
                    timeLine += '%3d ' % (self.intervalData[icount][key]['cpuPer'])
                SystemInfo.addPrint("%16s(%5s/%5s): " % (value['comm'], key, value['tgid']) + timeLine + '\n')

                if SystemInfo.graphEnable == True:
                    subplot(2,1,2)
                    timeLineData = [int(n) for n in timeLine.split()]
                    plot(range(SystemInfo.intervalEnable, (len(timeLineData)+1)*SystemInfo.intervalEnable, SystemInfo.intervalEnable), timeLineData, '.-')
                    SystemInfo.graphLabels.append(value['comm'])

                if value['usage'] / float(self.totalTime) * 100 < 1 and SystemInfo.showAll == False:
                    break;

        if SystemInfo.graphEnable == True:
            title('CPU Usage of Threads')
            ylabel('Percentage(%)', fontsize=10)
            legend(SystemInfo.graphLabels, bbox_to_anchor=(1.135, 1.02))
            del SystemInfo.graphLabels[:]
            figure(num=1, figsize=(20, 20), dpi=200, facecolor='b', edgecolor='k')
            savefig("cpuInfo.png",dpi=(200))
            clf()

        SystemInfo.pipePrint("%s# %s\n" % ('', 'CPU(%)'))
        SystemInfo.pipePrint(SystemInfo.bufferString)
        SystemInfo.pipePrint(oneLine)

        # Preempted timeline #
        SystemInfo.clearPrint()
        for key,value in sorted(self.threadData.items(), key=lambda e: e[1]['cpuWait'], reverse=True):
            if key[0:2] != '0[':
                icount = 0
                timeLine = ''
                for icount in range(0, int(float(self.totalTime) / SystemInfo.intervalEnable) + 1):
                    try: self.intervalData[icount][key]
                    except:
                        timeLine += '%3d ' % 0
                        continue
                    timeLine += '%3d ' % (self.intervalData[icount][key]['preempted'] / float(SystemInfo.intervalEnable) * 100)
                SystemInfo.addPrint("%16s(%5s/%5s): " % (value['comm'], key, value['tgid']) + timeLine + '\n')

                if value['cpuWait'] / float(self.totalTime) * 100 < 1 and SystemInfo.showAll == False:
                    break;

        SystemInfo.pipePrint("%s# %s\n" % ('', 'Delay(%)'))
        SystemInfo.pipePrint(SystemInfo.bufferString)
        SystemInfo.pipePrint(oneLine)

        # Block timeline #
        SystemInfo.clearPrint()
        for key,value in sorted(self.threadData.items(), key=lambda e: e[1]['reqBlock'], reverse=True):
            if key[0:2] != '0[':
                icount = 0
                timeLine = ''
                for icount in range(0, int(float(self.totalTime) / SystemInfo.intervalEnable) + 1):
                    try: self.intervalData[icount][key]
                    except:
                        timeLine += '%3d ' % 0
                        continue
                    timeLine += '%3d ' % (self.intervalData[icount][key]['ioUsage'] * SystemInfo.blockSize / 1024 / 1024)
                SystemInfo.addPrint("%16s(%5s/%5s): " % (value['comm'], key, value['tgid']) + timeLine + '\n')

                if SystemInfo.graphEnable == True:
                    subplot(2,1,1)
                    timeLineData = [int(n) for n in timeLine.split()]
                    plot(range(SystemInfo.intervalEnable, (len(timeLineData)+1)*SystemInfo.intervalEnable, SystemInfo.intervalEnable), timeLineData, '.-')
                    SystemInfo.graphLabels.append(value['comm'])

                if value['readBlock'] < 1 and SystemInfo.showAll == False:
                    break;

        if SystemInfo.graphEnable == True:
            title('Disk Usage of Threads')
            ylabel('Size(MB)', fontsize=10)
            legend(SystemInfo.graphLabels, bbox_to_anchor=(1.135, 1.02))
            del SystemInfo.graphLabels[:]

        SystemInfo.pipePrint("%s# %s\n" % ('', 'BLK_RD(MB)'))
        SystemInfo.pipePrint(SystemInfo.bufferString)
        SystemInfo.pipePrint(oneLine)

        # Memory timeline #
        SystemInfo.clearPrint()
        if SystemInfo.memEnable == True:
            for key,value in sorted(self.threadData.items(), key=lambda e: e[1]['nrPages'], reverse=True):
                if key[0:2] != '0[':
                    icount = 0
                    timeLine = ''
                    for icount in range(0, int(float(self.totalTime) / SystemInfo.intervalEnable) + 1):
                        try: self.intervalData[icount][key]
                        except:
                            timeLine += '%3d ' % 0
                            continue
                        timeLine += '%3d ' % \
                                ((self.intervalData[icount][key]['memUsage'] * 4 / 1024) + \
                                (self.intervalData[icount][key]['kmemUsage'] / 1024 / 1024))
                    SystemInfo.addPrint("%16s(%5s/%5s): " % (value['comm'], key, value['tgid']) + timeLine + '\n')

                    if SystemInfo.graphEnable == True:
                        subplot(2,1,2)
                        timeLineData = [int(n) for n in timeLine.split()]
                        plot(range(SystemInfo.intervalEnable, \
                                (len(timeLineData)+1)*SystemInfo.intervalEnable, SystemInfo.intervalEnable), timeLineData, '.-')
                        SystemInfo.graphLabels.append(value['comm'])

                    if (value['nrPages'] * 4 / 1024) + (value['remainKmem'] / 1024 / 1024) < 1 and SystemInfo.showAll == False:
                        break;

            SystemInfo.pipePrint("%s# %s\n" % ('', 'MEM(MB)'))
            SystemInfo.pipePrint(SystemInfo.bufferString)
            SystemInfo.pipePrint(oneLine)

            if SystemInfo.graphEnable == True:
                title('MEM Usage of Threads')
                ylabel('Size(MB)', fontsize=10)
                legend(SystemInfo.graphLabels, bbox_to_anchor=(1.135, 1.02))
                del SystemInfo.graphLabels[:]

        if SystemInfo.graphEnable == True:
            figure(num=1, figsize=(20, 20), dpi=200, facecolor='b', edgecolor='k')
            savefig("ioInfo.png",dpi=(200))





    @staticmethod
    def getInitTime(file):
        readLineCnt = 0
        try:
            f = open(file, 'r')

            while True:
                # Make delay because some filtered logs are not wrote soon #
                if readLineCnt > 30:
                    time.sleep(0.1)

                if readLineCnt > 50:
                    SystemInfo.printError("Fail to recognize format: Log is corrupted / There is no log collected / Filter is wrong")
                    SystemInfo.runRecordStopCmd()
                    sys.exit(0)

                l = f.readline()

                readLineCnt += 1

                m = re.match('^\s*(?P<comm>\S+)-(?P<thread>[0-9]+)\s+\(\s*(?P<tgid>\S+)\)\s+\[(?P<core>[0-9]+)\]\s+(?P<time>\S+):\s+(?P<func>\S+):(?P<etc>.+)', l)
                if m is not None:
                    d = m.groupdict()
                    f.close()
                    return d['time']

                m = re.match('^\s*(?P<comm>\S+)-(?P<thread>[0-9]+)\s+\[(?P<core>[0-9]+)\]\s+(?P<time>\S+):\s+(?P<func>\S+):(?P<etc>.+)', l)
                if m is not None:
                    d = m.groupdict()
                    f.close()
                    SystemInfo.tgidEnable = False
                    return d['time']

        except IOError:
            SystemInfo.printError("Fail to open %s" % file)
            sys.exit(0)



    def parse(self, string):
        SystemInfo.curLine += 1
        SystemInfo.printProgress()

        if SystemInfo.tgidEnable is True:
            m = re.match('^\s*(?P<comm>.+)-(?P<thread>[0-9]+)\s+\(\s*(?P<tgid>\S+)\)\s+\[(?P<core>[0-9]+)\]\s+(?P<time>\S+):\s+(?P<func>\S+):(?P<etc>.+)', string)
        else:
            m = re.match('^\s*(?P<comm>.+)-(?P<thread>[0-9]+)\s+\[(?P<core>[0-9]+)\]\s+(?P<time>\S+):\s+(?P<func>\S+):(?P<etc>.+)', string)
        if m is not None:
            d = m.groupdict()
            comm = d['comm']
            core = str(int(d['core']))
            func = d['func']
            etc = d['etc']
            time = d['time']

            SystemInfo.logSize += len(string)

            if SystemInfo.maxCore < int(core):
                SystemInfo.maxCore = int(core)

            coreId = '0' + '['  + core + ']'
            if int(d['thread']) == 0:
                thread = coreId
                comm = comm.replace("<idle>", "swapper/" + core);
            else: thread = d['thread']

            # make core thread entity in advance for total irq per core #
            try: self.threadData[coreId]
            except:
                self.threadData[coreId] = dict(self.init_threadData)
                self.threadData[coreId]['comm'] = "swapper/" + core

            # make thread entity #
            try: self.threadData[thread]
            except:
                self.threadData[thread] = dict(self.init_threadData)
                self.threadData[thread]['comm'] = comm

            if SystemInfo.tgidEnable is True:
                self.threadData[thread]['tgid'] = d['tgid']

            # calculate usage of threads had been running longer than interval #
            if SystemInfo.intervalEnable > 0:
                try:
                    for key,value in sorted(self.lastTidPerCore.items()):
                        if float(time) - float(self.threadData[self.lastTidPerCore[key]]['start']) > SystemInfo.intervalEnable / 1000:
                            self.threadData[self.lastTidPerCore[key]]['usage'] += float(time) - float(self.threadData[self.lastTidPerCore[key]]['start'])
                            self.threadData[self.lastTidPerCore[key]]['start'] = float(time)
                except: None

            if self.startTime == '0':
                self.startTime = time
            else:
                # set the time of last log in advance #
                if self.lastLog == string:
                    self.finishTime = time

                # calculate usage of threads in interval #
                if SystemInfo.intervalEnable > 0:
                    if float(time) - float(self.startTime)  > float(SystemInfo.intervalNow + SystemInfo.intervalEnable) \
                                                or self.finishTime != '0':
                        SystemInfo.intervalNow += SystemInfo.intervalEnable

                        for key,value in sorted(self.threadData.items(), key=lambda e: e[1]['usage'], reverse=True):
                            index = int(SystemInfo.intervalNow / SystemInfo.intervalEnable) - 1
                            nextIndex = int(SystemInfo.intervalNow / SystemInfo.intervalEnable)

                            try: self.intervalData[index]
                            except: self.intervalData.append({})
                            try: self.intervalData[index][key]
                            except: self.intervalData[index][key] = dict(self.init_intervalData)
                            try: self.intervalData[index]['toTal']
                            except: self.intervalData[index]['toTal'] = {'totalIo': int(0), 'totalMem': int(0), 'totalKmem': int(0)}
                            intervalThread = self.intervalData[index][key]

                            # save start time in this interval #
                            intervalThread['firstLogTime'] = float(time)

                            try: self.intervalData[nextIndex]
                            except: self.intervalData.append({})
                            try: self.intervalData[nextIndex][key]
                            except: self.intervalData[nextIndex][key] = dict(self.init_intervalData)
                            nextIntervalThread = self.intervalData[nextIndex][key]

                            # save total usage in this interval #
                            intervalThread['totalUsage'] = float(self.threadData[key]['usage'])
                            intervalThread['totalPreempted'] = float(self.threadData[key]['cpuWait'])
                            intervalThread['totalCoreSchedCnt'] = float(self.threadData[key]['coreSchedCnt'])
                            intervalThread['totalIoUsage'] = float(self.threadData[key]['reqBlock'])
                            intervalThread['totalMemUsage'] = float(self.threadData[key]['nrPages'])
                            intervalThread['totalKmemUsage'] = float(self.threadData[key]['remainKmem'])

                            # add time not calculated yet in this interval to related threads #
                            for idx, val in self.lastTidPerCore.items():
                                intervalThread['totalUsage'] += (float(time) - float(self.threadData[val]['start']))

                            # first interval #
                            if SystemInfo.intervalNow - SystemInfo.intervalEnable == 0:
                                intervalThread['cpuUsage'] += float(self.threadData[key]['usage'])
                                intervalThread['preempted'] += float(self.threadData[key]['cpuWait'])
                                intervalThread['coreSchedCnt'] = float(self.threadData[key]['coreSchedCnt'])
                                intervalThread['ioUsage'] = float(self.threadData[key]['reqBlock'])
                                intervalThread['memUsage'] = float(self.threadData[key]['nrPages'])
                                intervalThread['kmemUsage'] = float(self.threadData[key]['remainKmem'])
                            # normal intervals #
                            else:
                                try: self.intervalData[index - 1][key]
                                except: self.intervalData[index - 1][key] = dict(self.init_intervalData)
                                prevIntervalThread = self.intervalData[index - 1][key]

                                intervalThread['cpuUsage'] += intervalThread['totalUsage'] - prevIntervalThread['totalUsage']
                                intervalThread['preempted'] += intervalThread['totalPreempted'] - prevIntervalThread['totalPreempted']
                                intervalThread['coreSchedCnt'] = intervalThread['totalCoreSchedCnt'] - prevIntervalThread['totalCoreSchedCnt']
                                intervalThread['ioUsage'] = intervalThread['totalIoUsage'] - prevIntervalThread['totalIoUsage']
                                intervalThread['memUsage'] = intervalThread['totalMemUsage'] - prevIntervalThread['totalMemUsage']
                                intervalThread['kmemUsage'] = intervalThread['totalKmemUsage'] - prevIntervalThread['totalKmemUsage']

                            # fix cpu usage exceed this interval #
                            self.thisInterval = SystemInfo.intervalEnable
                            if intervalThread['cpuUsage'] > SystemInfo.intervalEnable or self.finishTime != '0':
                                # first interval #
                                if index == 0:
                                    self.thisInterval = float(time) - float(self.startTime)
                                # normal intervals #
                                elif float(self.intervalData[index - 1][key]['firstLogTime']) > 0:
                                    self.thisInterval = float(time) - float(self.intervalData[index - 1][key]['firstLogTime'])
                                # long time running intervals #
                                else:
                                    for idx in range(index - 1, -1, -1):
                                        if float(self.intervalData[index - 1][key]['firstLogTime']) > 0:
                                            self.thisInterval = float(time) - float(self.intervalData[idx][key]['firstLogTime'])
                                            break
                                    if self.thisInterval != SystemInfo.intervalEnable:
                                        self.thisInterval = float(time) - float(self.startTime)

                                # recalculate previous intervals if there was no context switching since profile start #
                                remainTime = intervalThread['cpuUsage']
                                if intervalThread['cpuUsage'] > self.thisInterval:
                                    for idx in range(int(intervalThread['cpuUsage'] / SystemInfo.intervalEnable), -1, -1):
                                        try: self.intervalData[idx][key]
                                        except: self.intervalData[idx][key] = dict(self.init_intervalData)
                                        try: self.intervalData[idx - 1][key]
                                        except: self.intervalData[idx - 1][key] = dict(self.init_intervalData)
                                        prevIntervalData = self.intervalData[idx - 1][key]

                                        # make previous intervals of core there was no context switching #
                                        longRunCore = self.threadData[key]['longRunCore']
                                        if longRunCore >= 0:
                                            longRunCoreId = '0[' + longRunCore + ']'
                                            try: self.intervalData[idx][longRunCoreId]
                                            except: self.intervalData[idx][longRunCoreId] = dict(self.init_intervalData)

                                        if remainTime >= SystemInfo.intervalEnable:
                                            remainTime = int(remainTime / SystemInfo.intervalEnable) * SystemInfo.intervalEnable
                                            prevIntervalData['cpuUsage'] = SystemInfo.intervalEnable
                                            prevIntervalData['cpuPer'] = 100
                                        else:
                                            if prevIntervalData['cpuUsage'] > remainTime:
                                                remainTime = prevIntervalData['cpuUsage']
                                            else:
                                                prevIntervalData['cpuUsage'] = remainTime
                                            prevIntervalData['cpuPer'] = remainTime / SystemInfo.intervalEnable * 100

                                        remainTime -= SystemInfo.intervalEnable

                            # add remainter of cpu usage exceed interval in this interval to previous interval #
                            if SystemInfo.intervalNow - SystemInfo.intervalEnable > 0 and self.thisInterval > SystemInfo.intervalEnable:
                                diff = self.thisInterval - SystemInfo.intervalEnable
                                if prevIntervalThread['cpuUsage'] + diff > SystemInfo.intervalEnable:
                                    diff = SystemInfo.intervalEnable - prevIntervalThread['cpuUsage']

                                prevIntervalThread['cpuUsage'] += diff
                                prevIntervalThread['cpuPer'] = prevIntervalThread['cpuUsage'] / SystemInfo.intervalEnable * 100

                            # calculate percentage of cpu usage of this thread in this interval #
                            intervalThread['cpuPer'] = intervalThread['cpuUsage'] / self.thisInterval * 100

                            # fix preempted time exceed this interval #
                            if intervalThread['preempted'] > SystemInfo.intervalEnable:
                                # recalculate previous intervals if there was no context switching since profile start #
                                remainTime = intervalThread['preempted']
                                if intervalThread['preempted'] > self.thisInterval:
                                    for idx in range(index + 1, -1, -1):
                                        try: self.intervalData[idx][key]
                                        except: self.intervalData[idx][key] = dict(self.init_intervalData)
                                        try: self.intervalData[idx - 1][key]
                                        except: self.intervalData[idx - 1][key] = dict(self.init_intervalData)

                                        if remainTime >= SystemInfo.intervalEnable:
                                            self.intervalData[idx - 1][key]['preempted'] = SystemInfo.intervalEnable
                                        else:
                                            self.intervalData[idx - 1][key]['preempted'] += remainTime

                                        remainTime -= SystemInfo.intervalEnable
                                        if remainTime <= 0:
                                            break

                            # calculate block usage of this thread in this interval #
                            self.intervalData[index]['toTal']['totalIo'] += self.intervalData[index][key]['ioUsage']

                            # calculate memory usage of this thread in this interval except for core threads because its already calculated #
                            if key[0:2] == '0[': continue
                            self.intervalData[index]['toTal']['totalMem'] += self.intervalData[index][key]['memUsage']
                            self.intervalData[index]['toTal']['totalKmem'] += self.intervalData[index][key]['kmemUsage']

            if func == "sched_switch":
                m = re.match('^\s*prev_comm=(?P<prev_comm>.*)\s+prev_pid=(?P<prev_pid>[0-9]+)\s+prev_prio=(?P<prev_prio>\S+)\s+prev_state=(?P<prev_state>\S+)\s+==>\s+next_comm=(?P<next_comm>.*)\s+next_pid=(?P<next_pid>[0-9]+)\s+next_prio=(?P<next_prio>\S+)', etc)
                if m is not None:
                    d = m.groupdict()

                    self.cxtSwitch += 1

                    prev_comm = d['prev_comm']
                    prev_pid = d['prev_pid']
                    prev_id = prev_pid
                    prev_state = d['prev_state']

                    if int(d['prev_pid']) == 0:
                        prev_id = d['prev_pid'] + '[' + str(int(core)) + ']'
                    else: prev_id = prev_pid

                    next_comm = d['next_comm']
                    next_pid = d['next_pid']
                    if int(d['next_pid']) == 0:
                        next_id = d['next_pid'] + '[' + str(int(core)) + ']'
                    else: next_id = next_pid

                    # make list #
                    try: self.threadData[prev_id]
                    except:
                        self.threadData[prev_id] = dict(self.init_threadData)
                        self.threadData[prev_id]['comm'] = prev_comm
                    try: self.threadData[next_id]
                    except:
                        self.threadData[next_id] = dict(self.init_threadData)
                        self.threadData[next_id]['comm'] = next_comm
                    try: self.threadData['0[' + core + ']']
                    except:
                        self.threadData['0[' + core + ']'] = dict(self.init_threadData)
                        self.threadData['0[' + core + ']']['comm'] = 'swapper/' + core

                    if self.wakeupData['valid'] > 0 and self.wakeupData['tid'] == prev_id:
                        self.wakeupData['valid'] -= 1

                    # update anonymous comm #
                    if comm == '<...>':
                        comm = prev_comm
                    if self.threadData[prev_id]['comm'] == '<...>':
                        self.threadData[prev_id]['comm'] = prev_comm
                    if self.threadData[next_id]['comm'] == '<...>':
                        self.threadData[next_id]['comm'] = next_comm

                    # write current time #
                    self.threadData[prev_id]['stop'] = float(time)
                    self.threadData[next_id]['start'] = float(time)
                    self.threadData[next_id]['waitStartAsParent'] = float(0)

                    # update priority of thread to highest #
                    if self.threadData[prev_id]['pri'] == '0' or int(self.threadData[prev_id]['pri']) > int(d['prev_prio']):
                        self.threadData[prev_id]['pri'] = d['prev_prio']
                    if self.threadData[next_id]['pri'] == '0' or int(self.threadData[next_id]['pri']) > int(d['next_prio']):
                        self.threadData[next_id]['pri'] = d['next_prio']

                    # calculate running time of prev_process #
                    diff = 0
                    if self.threadData[prev_id]['start'] <= 0:
                        # calculate running time of prev_process started before starting to profile #
                        diff = float(time) - float(self.startTime)
                        self.threadData[prev_id]['usage'] = diff
                    else:
                        diff = self.threadData[prev_id]['stop'] - self.threadData[prev_id]['start']
                        self.threadData[prev_id]['usage'] += diff

                        if self.threadData[prev_id]['maxRuntime'] < diff:
                            self.threadData[prev_id]['maxRuntime'] = diff

                    if diff > int(SystemInfo.intervalEnable):
                        self.threadData[prev_id]['longRunCore'] = core

                    # update core sched count #
                    self.threadData['0[' + core + ']']['coreSchedCnt'] += 1

                    # calculate preempted time of threads blocked #
                    if SystemInfo.preemptGroup != None:
                        for value in SystemInfo.preemptGroup:
                            index = SystemInfo.preemptGroup.index(value)
                            if self.preemptData[index][0] == True and self.preemptData[index][3] == core:
                                try: self.preemptData[index][1][prev_id]
                                except: self.preemptData[index][1][prev_id] = dict(self.init_preemptData)

                                self.preemptData[index][1][prev_id]['usage'] +=  \
                                self.threadData[prev_id]['stop'] - self.threadData[prev_id]['start']
                                self.preemptData[index][4] += self.threadData[prev_id]['stop'] - self.threadData[prev_id]['start']

                    if d['prev_state'][0] == 'R':
                        self.threadData[prev_id]['preempted'] += 1
                        self.threadData[next_id]['preemption'] += 1
                        self.threadData[prev_id]['lastStatus'] = 'P'

                        if SystemInfo.preemptGroup != None:
                            # enable preempted bit #
                            try: index = SystemInfo.preemptGroup.index(prev_id)
                            except: index = -1

                            if index >= 0:
                                self.preemptData[index][0] = True
                                try: self.preemptData[index][1][next_id]
                                except: self.preemptData[index][1][next_id] = dict(self.init_preemptData)

                                self.preemptData[index][2] = float(time)
                                self.preemptData[index][3] = core

                    elif d['prev_state'][0] == 'S':
                        self.threadData[prev_id]['yield'] += 1
                        self.threadData[prev_id]['stop'] = 0
                        self.threadData[prev_id]['lastStatus'] = 'S'

                    else:
                        self.threadData[prev_id]['stop'] = 0
                        self.threadData[prev_id]['lastStatus'] = d['prev_state'][0]

                    # calculate preempted time of next_process #
                    self.lastTidPerCore[core] = next_id
                    if self.threadData[next_id]['stop'] <= 0:
                        # no stop time of next_id #
                        self.threadData[next_id]['stop'] = 0
                    else:
                        if self.threadData[next_id]['lastStatus'] == 'P':
                            preemptedTime = self.threadData[next_id]['start'] - self.threadData[next_id]['stop']
                            self.threadData[next_id]['cpuWait'] +=  preemptedTime
                            if preemptedTime > self.threadData[next_id]['maxPreempted']:
                                self.threadData[next_id]['maxPreempted'] = preemptedTime

                            try: self.preemptData[SystemInfo.preemptGroup.index(next_id)][0] = False
                            except: None

            elif func == "irq_handler_entry":
                m = re.match('^\s*irq=(?P<irq>[0-9]+)\s+name=(?P<name>\S+)', etc)
                if m is not None:
                    d = m.groupdict()

                    irqId = 'irq/' + d['irq']

                    # make list #
                    try: self.irqData[irqId]
                    except: self.irqData[irqId] = dict(self.init_irqData)

                    if self.irqData[irqId]['start'] > 0:
                        diff = float(time) - self.irqData[irqId]['start']
                        if diff > self.irqData[irqId]['max_period'] or self.irqData[irqId]['max_period'] <= 0:
                            self.irqData[irqId]['max_period'] = diff
                        if diff < self.irqData[irqId]['min_period'] or self.irqData[irqId]['min_period'] <= 0:
                            self.irqData[irqId]['min_period'] = diff

                    self.irqData[irqId]['start'] = float(time)
                    self.irqData[irqId]['name'] = d['name']
                    self.irqData[irqId]['count'] += 1

            elif func == "irq_handler_exit":
                m = re.match('^\s*irq=(?P<irq>[0-9]+)\s+ret=(?P<return>\S+)', etc)
                if m is not None:
                    d = m.groupdict()

                    irqId = 'irq/' + d['irq']

                    # make list #
                    try: self.irqData[irqId]
                    except: self.irqData[irqId] = dict(self.init_irqData)

                    if self.irqData[irqId]['start'] > 0:
                        diff = float(time) - self.irqData[irqId]['start']
                        self.irqData[irqId]['usage'] += diff
                        self.threadData[thread]['irq'] += diff
                        if thread is not coreId:
                            self.threadData[coreId]['irq'] += diff

                        if diff > self.irqData[irqId]['max'] or self.irqData[irqId]['max'] <= 0:
                            self.irqData[irqId]['max'] = diff
                        if diff < self.irqData[irqId]['min'] or self.irqData[irqId]['min'] <= 0:
                            self.irqData[irqId]['min'] = diff

            elif func == "softirq_entry":
                m = re.match('^\s*vec=(?P<vector>[0-9]+)\s+\[action=(?P<action>\S+)\]', etc)
                if m is not None:
                    d = m.groupdict()

                    irqId = 'softirq/' + d['vector']

                    # make list #
                    try: self.irqData[irqId]
                    except:
                        self.irqData[irqId] = dict(self.init_irqData)
                        self.irqData[irqId]['name'] = d['action']

                    if self.irqData[irqId]['start'] > 0:
                        diff = float(time) - self.irqData[irqId]['start']
                        if diff > self.irqData[irqId]['max_period'] or self.irqData[irqId]['max_period'] <= 0:
                            self.irqData[irqId]['max_period'] = diff
                        if diff < self.irqData[irqId]['min_period'] or self.irqData[irqId]['min_period'] <= 0:
                            self.irqData[irqId]['min_period'] = diff

                    self.irqData[irqId]['start'] = float(time)
                    self.irqData[irqId]['count'] += 1

            elif func == "softirq_exit":
                m = re.match('^\s*vec=(?P<vector>[0-9]+)\s+\[action=(?P<action>\S+)\]', etc)
                if m is not None:
                    d = m.groupdict()

                    irqId = 'softirq/' + d['vector']

                    # make list #
                    try: self.irqData[irqId]
                    except:
                        self.irqData[irqId] = dict(self.init_irqData)
                        self.irqData[irqId]['name'] = d['action']

                    if self.irqData[irqId]['start'] > 0:
                        diff = float(time) - self.irqData[irqId]['start']
                        self.irqData[irqId]['usage'] += diff
                        self.threadData[thread]['irq'] += diff

                        if diff > self.irqData[irqId]['max'] or self.irqData[irqId]['max'] <= 0:
                            self.irqData[irqId]['max'] = diff
                        if diff < self.irqData[irqId]['min'] or self.irqData[irqId]['min'] <= 0:
                            self.irqData[irqId]['min'] = diff

            elif func == "sched_migrate_task":
                m = re.match('^\s*comm=(?P<comm>.*)\s+pid=(?P<pid>[0-9]+)\s+prio=(?P<prio>[0-9]+)\s+orig_cpu=(?P<orig_cpu>[0-9]+)\s+dest_cpu=(?P<dest_cpu>[0-9]+)', etc)
                if m is not None:
                    d = m.groupdict()

                    pid = d['pid']

                    try: self.threadData[pid]
                    except:
                        self.threadData[pid] = dict(self.init_threadData)
                        self.threadData[pid]['comm'] = d['comm']

                    self.threadData[pid]['migrate'] += 1

                    # update core data for preempted info #
                    if SystemInfo.preemptGroup != None:
                        try: index = SystemInfo.preemptGroup.index(thread)
                        except: index = -1

                        if index >= 0: self.preemptData[index][3] = core

            elif func == "mm_page_alloc":
                m = re.match('^\s*page=(?P<page>\S+)\s+pfn=(?P<pfn>[0-9]+)\s+order=(?P<order>[0-9]+)\s+migratetype=(?P<mt>[0-9]+)\s+gfp_flags=(?P<flags>\S+)', etc)
                if m is not None:
                    d = m.groupdict()

                    SystemInfo.memEnable = True

                    page = d['page']
                    pfn = int(d['pfn'])
                    flags = d['flags']
                    order = int(d['order'])

                    self.threadData[thread]['nrPages'] += pow(2, order)
                    self.threadData[coreId]['nrPages'] += pow(2, order)

                    if flags.find('HIGHUSER') >= 0:
                        pageType = 'USER'
                        self.threadData[thread]['userPages'] += pow(2, order)
                        self.threadData[coreId]['userPages'] += pow(2, order)
                    elif flags.find('NOFS') >= 0:
                        pageType = 'CACHE'
                        self.threadData[thread]['cachePages'] += pow(2, order)
                        self.threadData[coreId]['cachePages'] += pow(2, order)
                    else:
                        pageType = 'KERNEL'
                        self.threadData[thread]['kernelPages'] += pow(2, order)
                        self.threadData[coreId]['kernelPages'] += pow(2, order)

                    # make PTE in page table #
                    for cnt in range(0, pow(2, order)):
                        pfnv = pfn + cnt

                        try:
                            self.pageTable[pfnv]
                            # this allocated page is not freed #
                            self.threadData[thread]['nrPages'] -= 1
                            self.threadData[coreId]['nrPages'] -= 1
                        except: self.pageTable[pfnv] = dict(self.init_pageData)

                        self.pageTable[pfnv]['tid'] = thread
                        self.pageTable[pfnv]['page'] = page
                        self.pageTable[pfnv]['flags'] = flags
                        self.pageTable[pfnv]['type'] = pageType
                        self.pageTable[pfnv]['time'] = time

            elif func == "mm_page_free":
                m = re.match('^\s*page=(?P<page>\S+)\s+pfn=(?P<pfn>[0-9]+)\s+order=(?P<order>[0-9]+)', etc)
                if m is not None:
                    d = m.groupdict()

                    SystemInfo.memEnable = True

                    page = d['page']
                    pfn = int(d['pfn'])
                    order = int(d['order'])

                    for cnt in range(0, pow(2, order)):
                        pfnv = pfn + cnt

                        try:
                            self.threadData[self.pageTable[pfnv]['tid']]['nrPages'] -= 1
                            self.threadData[coreId]['nrPages'] -= 1

                            if thread != self.pageTable[pfnv]['tid']:
                                self.threadData[self.pageTable[pfnv]['tid']]['reclaimedPages'] += 1
                                self.threadData[coreId]['reclaimedPages'] += 1

                            if self.pageTable[pfnv]['type'] is 'CACHE':
                                self.threadData[self.pageTable[pfnv]['tid']]['cachePages'] -= 1
                                self.threadData[coreId]['cachePages'] -= 1
                            elif self.pageTable[pfnv]['type'] is 'USER':
                                self.threadData[self.pageTable[pfnv]['tid']]['userPages'] -= 1
                                self.threadData[coreId]['userPages'] -= 1
                            elif self.pageTable[pfnv]['type'] is 'KERNEL':
                                self.threadData[self.pageTable[pfnv]['tid']]['kernelPages'] -= 1
                                self.threadData[coreId]['kernelPages'] -= 1

                            self.pageTable[pfnv] = {}
                            del self.pageTable[pfnv]
                        except:
                            # this page is allocated before starting profile #
                            self.threadData[thread]['anonReclaimedPages'] += 1
                            self.threadData[coreId]['anonReclaimedPages'] += 1

            elif func == "mm_filemap_delete_from_page_cache":
                m = re.match('^\s*dev (?P<major>[0-9]+):(?P<minor>[0-9]+) .+page=(?P<page>\S+)\s+pfn=(?P<pfn>[0-9]+)', etc)
                if m is not None:
                    d = m.groupdict()

                    SystemInfo.memEnable = True

                    major = d['major']
                    minor = d['minor']
                    page = d['page']
                    pfn = int(d['pfn'])

                    try: self.pageTable[pfn]['type'] = 'CACHE'
                    except: None

            elif func == "kmalloc":
                m = re.match('^\s*call_site=(?P<caller>\S+)\s+ptr=(?P<ptr>\S+)\s+bytes_req=(?P<req>[0-9]+)\s+bytes_alloc=(?P<alloc>[0-9]+)\s+gfp_flags=(?P<flags>\S+)', etc)
                if m is not None:
                    d = m.groupdict()

                    SystemInfo.memEnable = True

                    caller = d['caller']
                    ptr = d['ptr']
                    req = int(d['req'])
                    alloc = int(d['alloc'])

                    try:
                        self.kmemTable[ptr]
                        # some allocated object is not freed #
                    except: self.kmemTable[ptr] = dict(self.init_kmallocData)

                    self.kmemTable[ptr]['tid'] = thread
                    self.kmemTable[ptr]['caller'] = caller
                    self.kmemTable[ptr]['req'] = req
                    self.kmemTable[ptr]['alloc'] = alloc
                    self.kmemTable[ptr]['waste'] = alloc - req
                    self.kmemTable[ptr]['core'] = coreId

                    self.threadData[thread]['remainKmem'] += alloc
                    self.threadData[thread]['wasteKmem'] += alloc - req
                    self.threadData[coreId]['remainKmem'] += alloc
                    self.threadData[coreId]['wasteKmem'] += alloc - req

            elif func == "kfree":
                m = re.match('^\s*call_site=(?P<caller>\S+)\s+ptr=(?P<ptr>\S+)', etc)
                if m is not None:
                    d = m.groupdict()

                    SystemInfo.memEnable = True

                    caller = d['caller']
                    ptr = d['ptr']

                    try:
                        self.threadData[self.kmemTable[ptr]['tid']]['remainKmem'] -= self.kmemTable[ptr]['alloc']
                        self.threadData[self.kmemTable[ptr]['core']]['remainKmem'] -= self.kmemTable[ptr]['alloc']
                        self.threadData[self.kmemTable[ptr]['tid']]['wasteKmem'] -= self.kmemTable[ptr]['waste']
                        self.threadData[self.kmemTable[ptr]['core']]['wasteKmem'] -= self.kmemTable[ptr]['waste']
                    except:
                        # this allocated object is not logged or this object is allocated before starting profile #
                        return

            elif func == "sched_wakeup":
                m = re.match('^\s*comm=(?P<comm>.*)\s+pid=(?P<pid>[0-9]+)\s+prio=(?P<prio>[0-9]+)\s+success=(?P<success>[0-9]+)\s+target_cpu=(?P<target>[0-9]+)', etc)
                if m is not None:
                    d = m.groupdict()

                    target_comm = d['comm']
                    pid= d['pid']
                    prio = d['prio']
                    success= d['success']

                    if self.wakeupData['tid'] == '0':
                        self.wakeupData['time'] = float(time) - float(self.startTime)
                    elif thread[0] == '0' or pid == '0': None
                    elif self.wakeupData['valid'] > 0 \
                             and (self.wakeupData['from'] != self.wakeupData['tid'] or self.wakeupData['to'] != pid):
                        if self.wakeupData['valid'] == 1 and self.wakeupData['corrupt'] == '0':
                            try: kicker = self.threadData[self.wakeupData['tid']]['comm']
                            except: kicker = "NULL"
                            kicker_pid = self.wakeupData['tid']
                        else:
                            kicker = self.threadData[thread]['comm']
                            kicker_pid = thread
                        self.depData.append("\t%.3f/%.3f \t%16s(%4s) -> %16s(%4s) \t%s" % (round(float(time) - float(self.startTime), 7), \
                         round(float(time) - float(self.startTime) - float(self.wakeupData['time']), 7), kicker, \
                         kicker_pid, target_comm, pid, "kick"))

                        self.wakeupData['time'] = float(time) - float(self.startTime)
                        self.wakeupData['from'] = self.wakeupData['tid']
                        self.wakeupData['to'] = pid

            elif func == "sys_enter":
                m = re.match('^\s*NR (?P<nr>[0-9]+) (?P<args>.+)', etc)
                if m is not None:
                    d = m.groupdict()

                    nr = d['nr']
                    args = d['args']

                    if nr == SystemInfo.sysFutex:
                        n = re.match('^\s*(?P<uaddr>\S+), (?P<op>[0-9]+), (?P<val>\S+), (?P<timep>\S+),', d['args'])
                        if n is not None:
                            l = n.groupdict()

                            op = int(l['op']) % 10
                            if op == 0: self.threadData[thread]['futexEnter'] = float(time)

                    if self.wakeupData['tid'] == '0':
                        self.wakeupData['time'] = float(time) - float(self.startTime)

                    if nr == SystemInfo.sysWrite:
                        self.wakeupData['tid'] = thread
                        self.wakeupData['nr'] = nr
                        self.wakeupData['args'] = args
                        if self.wakeupData['valid'] > 0 and (self.wakeupData['tid'] == thread and self.wakeupData['from'] == comm): None
                        else:
                            self.wakeupData['valid'] += 1
                            if self.wakeupData['valid'] > 1: self.wakeupData['corrupt'] = '1'
                            else: self.wakeupData['corrupt'] = '0'

                    try: self.threadData[thread]['syscallInfo']
                    except: self.threadData[thread]['syscallInfo'] = {}
                    try: self.threadData[thread]['syscallInfo'][nr]
                    except: self.threadData[thread]['syscallInfo'][nr] = dict(self.init_syscallInfo)

                    self.threadData[thread]['syscallInfo'][nr]['last'] = float(time)

                    if len(SystemInfo.syscallList) > 0:
                        try: idx = SystemInfo.syscallList.index(nr)
                        except: idx = -1

                        if idx >= 0: self.sysuserCallData.append(['enter', time, thread, core, nr, args])
                    else: self.sysuserCallData.append(['enter', time, thread, core, nr, args])

            elif func == "sys_exit":
                m = re.match('^\s*NR (?P<nr>[0-9]+) = (?P<ret>[0-9]+)', etc)
                if m is not None:
                    d = m.groupdict()

                    nr = d['nr']
                    ret = d['ret']

                    if nr == SystemInfo.sysFutex and self.threadData[thread]['futexEnter'] > 0:
                        self.threadData[thread]['futexCnt'] += 1
                        futexTime = float(time) - self.threadData[thread]['futexEnter']
                        if futexTime > self.threadData[thread]['futexMax']:
                            self.threadData[thread]['futexMax'] = futexTime
                        self.threadData[thread]['futexTotal'] += futexTime
                        self.threadData[thread]['futexEnter'] = 0

                    if nr == SystemInfo.sysWrite and self.wakeupData['valid'] > 0:
                        self.wakeupData['valid'] -= 1
                    elif nr == SystemInfo.sysSelect or nr == SystemInfo.sysPoll or nr == SystemInfo.sysEpollwait:
                        if (self.lastJob[core]['job'] == "sched_switch" or self.lastJob[core]['job'] == "sched_wakeup") and \
                                self.lastJob[core]['prevWakeupTid'] != thread:
                            self.depData.append("\t%.3f/%.3f \t%16s %4s     %16s(%4s) \t%s" % (round(float(time) - float(self.startTime), 7), \
                            round(float(time) - float(self.startTime) - float(self.wakeupData['time']), 7), " ", " ", self.threadData[thread]['comm'], \
                            thread, "wakeup"))

                            self.wakeupData['time'] = float(time) - float(self.startTime)
                            self.lastJob[core]['prevWakeupTid'] = thread
                    elif nr == SystemInfo.sysRecv:
                        if self.lastJob[core]['prevWakeupTid'] != thread:
                            self.depData.append("\t%.3f/%.3f \t%16s %4s     %16s(%4s) \t%s" % (round(float(time) - float(self.startTime), 7), \
                            round(float(time) - float(self.startTime) - float(self.wakeupData['time']), 7), " ", " ", self.threadData[thread]['comm'], \
                            thread, "recv"))

                            self.wakeupData['time'] = float(time) - float(self.startTime)
                            self.lastJob[core]['prevWakeupTid'] = thread

                    try: self.threadData[thread]['syscallInfo']
                    except: self.threadData[thread]['syscallInfo'] = {}
                    try: self.threadData[thread]['syscallInfo'][nr]
                    except: self.threadData[thread]['syscallInfo'][nr] = dict(self.init_syscallInfo)

                    if self.threadData[thread]['syscallInfo'][nr]['last'] > 0:
                        diff = float(time) - self.threadData[thread]['syscallInfo'][nr]['last']
                        self.threadData[thread]['syscallInfo'][nr]['usage'] += diff
                        self.threadData[thread]['syscallInfo'][nr]['last'] = 0

                        if self.threadData[thread]['syscallInfo'][nr]['max'] == 0 or self.threadData[thread]['syscallInfo'][nr]['max'] < diff:
                            self.threadData[thread]['syscallInfo'][nr]['max'] = diff
                        if self.threadData[thread]['syscallInfo'][nr]['min'] <= 0 or self.threadData[thread]['syscallInfo'][nr]['min'] > diff:
                            self.threadData[thread]['syscallInfo'][nr]['min'] = diff
                        self.threadData[thread]['syscallInfo'][nr]['count'] += 1

                    if len(SystemInfo.syscallList) > 0:
                        try: idx = SystemInfo.syscallList.index(nr)
                        except: idx = -1

                        if idx >= 0: self.sysuserCallData.append(['exit', time, thread, core, nr, ret])
                    else: self.sysuserCallData.append(['exit', time, thread, core, nr, ret])

            elif func == "signal_generate":
                m = re.match('^\s*sig=(?P<sig>[0-9]+) errno=(?P<err>[0-9]+) code=(?P<code>[0-9]+) comm=(?P<comm>.*) pid=(?P<pid>[0-9]+)', etc)
                if m is not None:
                    d = m.groupdict()

                    sig = d['sig']
                    err = d['err']
                    code = d['code']
                    target_comm = d['comm']
                    pid = d['pid']

                    self.depData.append("\t%.3f/%.3f \t%16s(%4s) -> %16s(%4s) \t%s(%s)" % (round(float(time) - float(self.startTime), 7), \
                     round(float(time) - float(self.startTime) - float(self.wakeupData['time']), 7), self.threadData[thread]['comm'], \
                     thread, target_comm, pid, "sigsend", sig))

                    self.sigData.append(('SEND', float(time) - float(self.startTime), \
                     self.threadData[thread]['comm'], thread, target_comm, pid, sig))

                    self.wakeupData['time'] = float(time) - float(self.startTime)

                    try: self.threadData[pid]
                    except: return

                    # SIGCHLD #
                    if sig == '17':
                        if self.threadData[pid]['waitStartAsParent'] > 0:
                            if self.threadData[pid]['waitPid'] == 0 or self.threadData[pid]['waitPid'] == int(thread):
                                diff = float(time) - self.threadData[pid]['waitStartAsParent']
                                self.threadData[thread]['waitParent'] = diff
                                self.threadData[pid]['waitChild'] += diff

            elif func == "signal_deliver":
                m = re.match('^\s*sig=(?P<sig>[0-9]+) errno=(?P<err>[0-9]+) code=(?P<code>[0-9]+) sa_handler=(?P<handler>[0-9]+) sa_flags=(?P<flags>[0-9]+)', etc)
                if m is not None:
                    d = m.groupdict()

                    sig = d['sig']
                    err = d['err']
                    code = d['code']
                    handler = d['handler']
                    flags = d['flags']

                    self.depData.append("\t%.3f/%.3f \t%16s %4s     %16s(%4s) \t%s(%s)" % (round(float(time) - float(self.startTime), 7), \
                     round(float(time) - float(self.startTime) - float(self.wakeupData['time']), 7), "", "", \
                     self.threadData[thread]['comm'], thread, "sigrecv", sig))

                    self.sigData.append(('RECV', float(time) - float(self.startTime), \
                     None, None, self.threadData[thread]['comm'], thread, sig))

                    self.wakeupData['time'] = float(time) - float(self.startTime)

            elif func == "block_bio_remap":
                m = re.match('^\s*(?P<major>[0-9]+),(?P<minor>[0-9]+)\s*(?P<operation>\S+)\s*(?P<address>\S+)\s+\+\s+(?P<size>[0-9]+)', etc)
                if m is not None:
                    d = m.groupdict()

                    if d['operation'][0] == 'R':
                        bio = d['major'] + '/' + d['minor'] + '/' + d['operation'][0] + '/' + d['address']

                        self.ioData[bio] = {'thread': thread, 'time': float(time), 'major': d['major'], 'minor': d['minor'], \
                                'address': int(d['address']), 'size': int(d['size'])}

                        self.threadData[thread]['reqBlock'] += int(d['size'])
                        self.threadData[thread]['readCnt'] += 1
                        self.threadData[thread]['readBlockCnt'] += 1
                        self.threadData[coreId]['readBlockCnt'] += 1
                        if self.threadData[thread]['readStart'] == 0:
                            self.threadData[thread]['readStart'] = float(time)

            elif func == "block_rq_complete":
                m = re.match('^\s*(?P<major>[0-9]+),(?P<minor>[0-9]+)\s*(?P<operation>\S+)\s*\(\S*\s*\)\s*(?P<address>\S+)\s+\+\s+(?P<size>[0-9]+)', etc)
                if m is not None:
                    d = m.groupdict()

                    address = d['address']
                    size = d['size']

                    bio = d['major'] + '/' + d['minor'] + '/' + d['operation'][0] + '/' + d['address']


                    try:
                        self.threadData[self.ioData[bio]['thread']]
                        bioStart = int(address)
                        bioEnd = int(address) + int(size)
                    except: return

                    for key, value in sorted(self.ioData.items(), key=lambda e: e[1]['address'], reverse=False):
                        if self.ioData[key]['major'] == d['major'] and self.ioData[key]['minor'] == d['minor']:
                            if bioStart <= self.ioData[key]['address'] < bioEnd or \
                                    bioStart < self.ioData[key]['address'] + self.ioData[key]['size'] <= bioEnd:

                                matchBlock = 0

                                if bioStart < self.ioData[key]['address']: matchStart = self.ioData[key]['address']
                                else: matchStart = bioStart

                                if bioEnd > self.ioData[key]['address'] + self.ioData[key]['size']:
                                    matchEnd = self.ioData[key]['address'] + self.ioData[key]['size']
                                else: matchEnd = bioEnd

                                if matchStart == self.ioData[key]['address']:
                                    matchBlock = matchEnd - self.ioData[key]['address']
                                    self.ioData[key]['size'] = self.ioData[key]['address'] + self.ioData[key]['size'] - matchEnd
                                    self.ioData[key]['address'] = matchEnd
                                elif matchStart > self.ioData[key]['address']:
                                    if matchEnd == self.ioData[key]['address'] + self.ioData[key]['size']:
                                        matchBlock = matchEnd - matchStart
                                        self.ioData[key]['size'] = matchStart - self.ioData[key]['address']
                                    else:
                                        del self.ioData[key]
                                        continue
                                else:
                                    del self.ioData[key]
                                    continue

                                if bioEnd < self.ioData[key]['address'] + self.ioData[key]['size']: return

                                self.threadData[self.ioData[key]['thread']]['readBlock'] += matchBlock
                                self.threadData[coreId]['readBlock'] += matchBlock

                                if self.ioData[key]['size'] == 0:
                                    if self.threadData[self.ioData[key]['thread']]['readCnt'] > 0:
                                        self.threadData[self.ioData[key]['thread']]['readCnt'] -= 1

                                    if self.threadData[self.ioData[key]['thread']]['readStart'] > 0 and \
                                            self.threadData[self.ioData[key]['thread']]['readCnt'] == 0:
                                        self.threadData[coreId]['ioWait'] += \
                                                float(time) - self.threadData[self.ioData[key]['thread']]['readStart']
                                        self.threadData[self.ioData[key]['thread']]['ioWait'] += \
                                                float(time) - self.threadData[self.ioData[key]['thread']]['readStart']
                                        self.threadData[self.ioData[key]['thread']]['readStart'] = 0

                                    del self.ioData[key]

            elif func == "writeback_dirty_page":
                m = re.match('^\s*bdi\s+(?P<major>[0-9]+):(?P<minor>[0-9]+):\s*ino=(?P<ino>\S+)\s+index=(?P<index>\S+)', etc)
                if m is not None:
                    d = m.groupdict()

                    ino = d['ino']
                    index = d['index']

                    self.threadData[thread]['writeBlock'] += 1
                    self.threadData[thread]['writeBlockCnt'] += 1
                    self.threadData[coreId]['writeBlock'] += 1
                    self.threadData[coreId]['writeBlockCnt'] += 1

            elif func == "wbc_writepage":
                m = re.match('^\s*bdi\s+(?P<major>[0-9]+):(?P<minor>[0-9]+):\s*towrt=(?P<towrt>\S+)\s+skip=(?P<skip>\S+)', etc)
                if m is not None:
                    d = m.groupdict()

                    towrt = d['towrt']
                    skip = d['skip']

                    if skip == '0':
                        self.threadData[thread]['writeBlock'] += 1
                        self.threadData[thread]['writeBlockCnt'] += 1
                        self.threadData[coreId]['writeBlock'] += 1
                        self.threadData[coreId]['writeBlockCnt'] += 1

            elif func == "mm_vmscan_wakeup_kswapd":
                try: self.reclaimData[thread]
                except: self.reclaimData[thread] = {'start': float(0)}

                if self.reclaimData[thread]['start'] <= 0:
                    self.reclaimData[thread]['start'] = float(time)

                self.threadData[thread]['reclaimCnt'] += 1

            elif func == "mm_vmscan_kswapd_sleep":
                for key,value in self.reclaimData.items():
                    try: self.threadData[key]
                    except:
                        self.threadData[key] = dict(self.init_threadData)
                        self.threadData[key]['comm'] = comm

                    self.threadData[key]['reclaimWait'] += float(time) - float(value['start'])
                    del self.reclaimData[key]

            elif func == "mm_vmscan_direct_reclaim_begin":
                if self.threadData[thread]['dReclaimStart'] <= 0:
                    self.threadData[thread]['dReclaimStart'] = float(time)

                self.threadData[thread]['dReclaimCnt'] += 1
                self.threadData[coreId]['dReclaimCnt'] += 1

            elif func == "mm_vmscan_direct_reclaim_end":
                m = re.match('^\s*nr_reclaimed=(?P<nr>[0-9]+)', etc)
                if m is not None:
                    d = m.groupdict()

                    if self.threadData[thread]['dReclaimStart'] > 0:
                        self.threadData[thread]['dReclaimWait'] += float(time) - self.threadData[thread]['dReclaimStart']
                        self.threadData[coreId]['dReclaimWait'] += float(time) - self.threadData[thread]['dReclaimStart']

                    self.threadData[thread]['dReclaimStart'] = 0

            elif func == "task_newtask":
                m = re.match('^\s*pid=(?P<pid>[0-9]+)\s+comm=(?P<comm>\S+)', etc)
                if m is not None:
                    d = m.groupdict()

                    pid = d['pid']

                    try: self.threadData[pid]
                    except:
                        self.threadData[pid] = dict(self.init_threadData)
                        self.threadData[pid]['comm'] = d['comm']
                        self.threadData[pid]['ptid'] = thread
                        self.threadData[pid]['new'] = 'N'
                        self.threadData[pid]['createdTime'] = float(time)

                    if self.threadData[thread]['childList'] is None:
                        self.threadData[thread]['childList'] = list()

                    self.threadData[thread]['childList'].append(pid)

            elif func == "task_rename":
                m = re.match('^\s*pid=(?P<pid>[0-9]+)\s+oldcomm=(?P<oldcomm>.*)\s+newcomm=(?P<newcomm>.*)\s+oom_score_adj', etc)
                if m is not None:
                    d = m.groupdict()

                    pid = d['pid']
                    newcomm = d['newcomm']

                    try: self.threadData[pid]
                    except:
                        self.threadData[pid] = dict(self.init_threadData)
                        self.threadData[pid]['comm'] = newcomm
                        self.threadData[pid]['ptid'] = thread

                    self.threadData[pid]['comm'] = newcomm

            elif func == "sched_process_free":
                m = re.match('^\s*comm=(?P<comm>.*)\s+pid=(?P<pid>[0-9]+)', etc)
                if m is not None:
                    d = m.groupdict()

                    pid = d['pid']

                    try: self.threadData[pid]
                    except:
                        self.threadData[pid] = dict(self.init_threadData)
                        self.threadData[pid]['comm'] = d['comm']
                        self.threadData[pid]['die'] = '1'

                    self.threadData[pid]['die'] = 'D'

            elif func == "sched_process_wait":
                m = re.match('^\s*comm=(?P<comm>.*)\s+pid=(?P<pid>[0-9]+)', etc)
                if m is not None:
                    d = m.groupdict()

                    self.threadData[thread]['waitStartAsParent'] = float(time)
                    self.threadData[thread]['waitPid'] = int(d['pid'])

            elif func == "machine_suspend":
                m = re.match('^\s*state=(?P<state>[0-9]+)', etc)
                if m is not None:
                    d = m.groupdict()

                    if int(d['state']) == 3 : state = 'S'
                    else: state = 'R'

                    self.suspendData.append([time, state])

            elif func == "cpu_idle":
                m = re.match('^\s*state=(?P<state>[0-9]+)\s+cpu_id=(?P<cpu_id>[0-9]+)', etc)
                if m is not None:
                    d = m.groupdict()

                    tid = '0[' + d['cpu_id']+ ']'

                    if self.threadData[tid]['lastIdleStatus'] == int(d['state']): return
                    else: self.threadData[tid]['lastIdleStatus'] = int(d['state'])

                    if self.threadData[tid]['coreSchedCnt'] == 0 and self.threadData[tid]['offTime'] == 0:
                        self.threadData[tid]['offTime'] = float(time) - float(self.startTime)

                    # Wake core up, but the number 3 as this condition is not certain #
                    if int(d['state']) < 3:
                        self.threadData[tid]['offCnt'] += 1
                        self.threadData[tid]['lastOff'] = float(time)
                    # Start to sleep #
                    else:
                        if self.threadData[tid]['lastOff'] > 0:
                            self.threadData[tid]['offTime'] += float(time) - self.threadData[tid]['lastOff']
                            self.threadData[tid]['lastOff'] = float(0)

            elif func == "cpu_frequency":
                # toDo: calculate power consumption for DFVS system #
                None

            elif func == "console":
                m = re.match('^\s*\[\s*(?P<time>\S+)\s*\]\s+EVENT_(?P<event>\S+)', etc)
                if m is not None:
                    d = m.groupdict()

                    event = d['event']

                    # initialize ThreadInfo data #
                    if event == 'START':
                        self.threadData = {}
                        self.irqData = {}
                        self.ioData = {}
                        self.reclaimData = {}
                        self.pageTable = {}
                        self.kmemTable = {}
                        self.intervalData = []
                        self.depData = []
                        self.sysuserCallData = []
                        self.lastJob = {}
                        self.preemptData = []
                        self.suspendData = []
                        self.markData = []
                        self.consoleData = []
                        self.startTime = time
                        return
                    # finish data processing #
                    elif event == 'STOP':
                        self.finishTime = time
                        self.stopFlag = True
                        return
                    # restart data processing for compare #
                    elif event == 'RESTART':
                        self.threadDataOld = self.threadData
                        self.threadData = {}
                        self.irqDataOld = self.irqData
                        self.irqData = {}
                        self.ioDataOld = self.ioData
                        self.ioData = {}
                        self.reclaimDataOld = self.reclaimData
                        self.reclaimData = {}

                        self.totalTimeOld = round(float(time) - float(self.startTime), 7)
                        self.startTime = time
                        return
                    # saving mark event #
                    elif event == 'MARK':
                        self.markData.append(time)

                    ei.addEvent(time, event)
                else: self.consoleData.append([d['thread'], core, time, etc])

            elif func == "tracing_mark_write":
                m = re.match('^\s*EVENT_(?P<event>\S+)', etc)
                if m is not None:
                    d = m.groupdict()

                    event = d['event']

                    # initialize ThreadInfo data #
                    if event == 'START':
                        self.threadData = {}
                        self.irqData = {}
                        self.ioData = {}
                        self.reclaimData = {}
                        self.pageTable = {}
                        self.kmemTable = {}
                        self.intervalData = []
                        self.depData = []
                        self.sysuserCallData = []
                        self.lastJob = {}
                        self.preemptData = []
                        self.suspendData = []
                        self.markData = []
                        self.consoleData = []
                        self.startTime = time
                        return
                    # finish data processing #
                    elif event == 'STOP':
                        self.finishTime = time
                        self.stopFlag = True
                        return
                    # restart data processing for compare #
                    elif event == 'RESTART':
                        self.threadDataOld = self.threadData
                        self.threadData = {}
                        self.irqDataOld = self.irqData
                        self.irqData = {}
                        self.ioDataOld = self.ioData
                        self.ioData = {}
                        self.reclaimDataOld = self.reclaimData
                        self.reclaimData = {}

                        self.totalTimeOld = round(float(time) - float(self.startTime), 7)
                        self.startTime = time
                        return
                    # saving mark event #
                    elif event == 'MARK':
                        self.markData.append(time)

                    ei.addEvent(time, event)

            # save last job per core #
            try: self.lastJob[core]
            except: self.lastJob[core] = dict(self.init_lastJob)

            self.lastJob[core]['job'] = func
            self.lastJob[core]['time'] = time



    def compareThreadData(self):
        for key,value in sorted(ti.threadData.items(), key=lambda e: e[1]['usage'], reverse=True):
            newPercent = round(float(value['usage']) / float(ti.totalTime), 7) * 100

            try: ti.threadDataOld[key]
            except:
                if int(newPercent) < 1:
                    del ti.threadData[key]
                continue

            oldPercent = round(float(ti.threadDataOld[key]['usage']) / float(ti.totalTimeOld), 7) * 100
            if int(oldPercent) >= int(newPercent) or int(newPercent) < 1:
                del ti.threadData[key]





if __name__ == '__main__':

    oneLine = "-"*154
    twoLine = "="*154

    # print help #
    if len(sys.argv) <= 1:
        print("\n[ g.u.i.d.e.r \t%s ]\n" % __version__)
        print('Usage: \n\t# guider [command] [options]\n')
        print('Example: \n\t# guider record -s. -emi\n\t$ guider guider.dat -o. -a\n')
        print('Options: \n\t-b[set_perCpuBuffer:kb]\n\t-s[save_traceData:dir]\n\t-o[set_outputFile:dir]\n\t-r[record_repeatData:interval,count]')
        print('\n\t-e[enable_options:i(rq)|m(em)|f(utex)|g(raph)|p(ipe)|t(ty)]\n\t-d[disable_options:t(ty)]\n\t-c[ready_compareUsage]')
        print('\n\t-a[show_allEntity]\n\t-i[set_interval:sec]\n\t-g[show_onlyGroup:comms/tids]\n\t-q[make_taskchain]')
        print('\n\t-w[show_threadDependency]\n\t-p[show_preemptInfo:tids]\n\t-t[trace_syscall:syscallNums]')
        print('\n\t-f[run_functionProfileMode:event]\n\t-l[input_addr2linePath:file]\n\t-j[input_targetRootPath:dir]')
        print('\n\t-m[run_pageProfileMode]')
        print('\n')

        sys.exit(0)

    SystemInfo.inputFile = sys.argv[1]
    SystemInfo.outputFile = None

    # parse recording option #
    if SystemInfo.isRecordMode() is True:
        SystemInfo.inputFile = '/sys/kernel/debug/tracing/trace'

        # set this process to RT priority #
        SystemInfo.setRtPriority('90')

        # save system information #`
        si = SystemInfo()

        SystemInfo.parseRecordOption()

        if SystemInfo.functionEnable is not False:
            SystemInfo.printInfo("function profile mode")
            # si.runPeriodProc()
            # toDo: make periodic event every 100us for specific thread #
        elif SystemInfo.fileEnable is not False:
            SystemInfo.printInfo("file profile mode")
        else:
            SystemInfo.printInfo("thread profile mode")
            SystemInfo.threadEnable = True

        # set signal #
        if SystemInfo.repeatCount > 0 and SystemInfo.repeatInterval > 0 and SystemInfo.threadEnable is True:
            signal.signal(signal.SIGALRM, SystemInfo.alarmHandler)
            signal.alarm(SystemInfo.repeatInterval)
            if SystemInfo.outputFile is None:
                SystemInfo.printError("wrong option with -s, use parameter for saving data")
                sys.exit(0)
        else:
            SystemInfo.repeatInterval = 0
            SystemInfo.repeatCount = 0
            signal.signal(signal.SIGINT, SystemInfo.stopHandler)
            signal.signal(signal.SIGQUIT, SystemInfo.newHandler)

        # create FileInfo #
        if SystemInfo.fileEnable is not False:
            # parse additional option #
            SystemInfo.parseAddOption()

            # start file profiling #
            pi = FileInfo()
            sys.exit(0)

        # start recording for thread profile #
        SystemInfo.printStatus('start recording... [ STOP(ctrl + c), COMPARE(ctrl + \) ]')
        si.runRecordStartCmd()

        if SystemInfo.pipeEnable is True and SystemInfo.threadEnable is True:
            if SystemInfo.outputFile is not None:
                SystemInfo.setIdlePriority(0)
                SystemInfo.copyPipeToFile(SystemInfo.inputFile + '_pipe', SystemInfo.outputFile)
                SystemInfo.runRecordStopCmd()
                SystemInfo.runRecordStopFinalCmd()
                SystemInfo.printInfo("wrote output to %s successfully" % (SystemInfo.outputFile))
                sys.exit(0)
            else:
                SystemInfo.printError("wrong option with -ep, use also -s option for saving data")
                SystemInfo.runRecordStopFinalCmd()
                sys.exit(0)

        # get init time in buffer for verification #
        initTime = ThreadInfo.getInitTime(SystemInfo.inputFile)

        # enter loop to record and save data periodically #
        while SystemInfo.repeatInterval > 0:
            if SystemInfo.repeatCount == 0:
                SystemInfo.runRecordStopCmd()
                SystemInfo.runRecordStopFinalCmd()
                sys.exit(0)

            # get init time in buffer for verification #
            initTime = ThreadInfo.getInitTime(SystemInfo.inputFile)

            # wait for timer expire #
            signal.pause()

            if initTime != ThreadInfo.getInitTime(SystemInfo.inputFile) and SystemInfo.functionEnable is False:
                SystemInfo.printError("Buffer is not enough (%s KB) or Profile time is too long" % (si.getBufferSize()))
                SystemInfo.runRecordStopCmd()
                SystemInfo.runRecordStopFinalCmd()
                sys.exit(0)
            else: SystemInfo.clearTraceBuffer()

        # wait for user input #
        signal.pause()

        if initTime != ThreadInfo.getInitTime(SystemInfo.inputFile) and SystemInfo.functionEnable is False:
            SystemInfo.printError("Buffer size is not enough (%s KB) or Profile time is too long" % (si.getBufferSize()))
            SystemInfo.runRecordStopFinalCmd()
            sys.exit(0)

        # save system information after profiling
        si.saveMeminfo()

    # parse additional option #
    SystemInfo.parseAddOption()

    ThreadInfo.getInitTime(SystemInfo.inputFile)

    # set handler for exit #
    signal.signal(signal.SIGINT, SystemInfo.exitHandler)

    # create Function Info #
    if SystemInfo.functionEnable is not False:
        fi = FunctionInfo(SystemInfo.inputFile)

        # Disable options related to stacktrace #
        if SystemInfo.isRecordMode() is True: 
            SystemInfo.runRecordStopFinalCmd()

        # Print Function Info #
        fi.printUsage()

        sys.exit(0)

    # create Event Info #
    ei = EventInfo()

    if SystemInfo.graphEnable is True:
        try: from pylab import *
        except:
            SystemInfo.printWarning("making graph is not supported")
            SystemInfo.graphEnable = False

    # create Thread Info #
    ti = ThreadInfo(SystemInfo.inputFile)

    if SystemInfo.isRecordMode():
        si.printMemInfo()
        SystemInfo.runRecordStopFinalCmd()

    # print event info #
    ei.printEventInfo()

    # start input menu #
    if SystemInfo.selectMenu != None:
        # make file related to taskchain #
        ti.makeTaskChain()