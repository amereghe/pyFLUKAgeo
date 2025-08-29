# classes for managing FLUKA geometries
# A. Mereghetti, 2023/09/13
# python version: >= 3.8.10;

import numpy as np
from copy import deepcopy

import grid
from body import Body
from region import Region
from transformation import RotDefi, Transformation
from scorings import Usrbin, Usryield, Usrbdx, Usrtrack, Usrcoll
from FLUKA import HighLightComment, TailNameInt
from myMath import RotMat

class Geometry():
    '''
    - name-based FLUKA geometry defition;
    - NO support for #include cards or geo defitions in files other than that
       being parsed;
    - basic support for LATTICE cards at parsing:
      . no check of existence of lattice region or of transformations;
    - comments:
      . in general, only comments preceeding a specific card are retained;
      . body: commented lines are considered always before the body;
              --> trailing comments to body declaration section will disappear!
      . region: commented lines are kept where they are found, if they are
                found before or along the region declaration;
      . lattice: comments are ignored;
      . rot-defi: commented lines are considered always before the rot-defi card;
      . usrbin: commented lines are considered always before the URSBIN card;
    - #define vars used only at parsing level, i.e. they are not stored
      in the parsed geometry; only boolean #define vars for the time being,
      but any nesting level is supported;
    '''
    def __init__(self):
        self.bods=[]
        self.regs=[]
        self.tras=[]
        self.bins=[] # USRBINs
        self.scos=[] # other scoring cards (reg-based)
        self.title=""

    def add(self,tmpEl,what="body"):
        '''
        tmpEl is already the instance to be added, NOT the string buffer to be parsed
        '''
        if (what.upper().startswith("BOD")):
            self.bods.append(tmpEl)
        elif (what.upper().startswith("REG")):
            self.regs.append(tmpEl)
        elif (what.upper().startswith("TRAS") or what.upper().startswith("TRANSF")):
            self.tras.append(tmpEl)
        elif (what.upper().startswith("BIN") or what.upper().startswith("USRBIN")):
            self.bins.append(tmpEl)
        elif (what.upper().startswith("SCO") or what.upper().startswith("SCORING")):
            self.scos.append(tmpEl)
        else:
            print("...what do you want to add to geometry? %s NOT recognised!"%(what))
            exit(1)

    def setTitle(self,tmpTitle="My Geometry"):
        self.title=tmpTitle
        
    def assignma(self,tmpLine):
        '''
        crunch info by ASSIGNMA card
        - no additional info (e.g. magfield...)
        '''
        data=tmpLine.split()
        myMatName=data[1]
        myFirstRegName=data[2]
        if (len(data)>=4):
            myLastRegName=data[3]
        else:
            myLastRegName=None
        if (len(data)>=5):
            iStep=int(data[4])
        else:
            iStep=1
        self.AssignMaterial(myMatName,myFirstRegName,myLastRegName=myLastRegName,iStep=iStep)

    def AssignMaterial(self,myMatName,myFirstRegName,myLastRegName=None,iStep=1):
        '''function performing the actual material assignment'''
        myEntry,iFirst=self.ret("REG",myFirstRegName)
        if (myLastRegName is not None):
            myEntry,iLast=self.ret("REG",myLastRegName)
        else:
            iLast=iFirst
        for iEntry in range(iFirst,iLast+1,iStep):
            print("...assigning material %s to region %s..."%(myMatName,self.regs[iEntry].echoName()))
            self.regs[iEntry].assignMat(myMatName)

    def rotdefi(self,tmpBuf,lFree=True):
        'crunch info by ROT-DEFI card'
        tmpRotDefi,myID,myName=RotDefi.fromBuf(tmpBuf,lFree=lFree)
        myEntry,iEntry=self.ret("TRANSF",myName)
        if (iEntry==-1):
            if (myID==-1):
                myEntries,myIDs=self.ret("TRANSF","all")
                myID=len(myEntries)+1
            # brand new transformation
            self.add(Transformation(myID=myID,myName=myName),"TRANSF")
        self.tras[iEntry].AddRotDefi(tmpRotDefi)

    def lattice(self,tmpLine,lDebug=False):
        '''
        crunch info by LATTICE card:
        - only one lattice region;
        - only one lattice;
        '''
        data=tmpLine.split()
        myLatName=data[1]
        myRegName=data[2]
        myRotName=data[3]
        if (lDebug):
            print("...flagging region %s as lattice %s with transformation %s..."%(
                myRegName,myLatName,myRotName))
        myEntry,iEntry=self.ret("REG",myRegName)
        self.regs[iEntry].assignLat(myLatName)
        self.regs[iEntry].assignTrasf(myRotName)
        self.regs[iEntry].assignMat()

    def headMe(self,myString,begLine=None,endLine=None):
        '''
        simple method to head a string to the geometry declaration (bodies,
           regions, assignma, usrbin, rot-defi cards)
        '''
        actualString=HighLightComment(myString,begLine=begLine,endLine=endLine)
        if (len(self.bods)>0):
            self.bods[0].headMe(actualString)
        if (len(self.regs)>0):
            self.regs[0].headMe(actualString)
        if (len(self.tras)>0):
            self.tras[0].headMe(actualString)
        if (len(self.bins)>0):
            self.bins[0].headMe(actualString)
            
    def ret(self,myKey,myValue):
        lFound=False
        if (myKey.upper().startswith("BODSINREG")):
            if (myValue.upper()=="ALL"):
                myReg,iReg=self.ret("reg","ALL")
                myEntry=[]; iEntry=[]
                for findReg in myReg:
                    tmpEl,tmpInd=self.ret("BodsInReg",findReg)
                    myEntry=myEntry+tmpEl
                    iEntry=iEntry+tmpInd
            else:
                myReg,iReg=self.ret("reg",myValue)
                myEntry=myReg.retBodiesInDef()
                iEntry=[]
                for findBod in myEntry:
                    tmpEl,tmpInd=self.ret("bod",findBod)
                    iEntry.append(tmpInd)
                lFound=True
        elif (myKey.upper().startswith("BOD")):
            if (myValue.upper()=="ALL"):
                myEntry=[ body.echoName() for body in self.bods ]
                iEntry=[ ii for ii in range(len(self.bods)) ]
                lFound=True
            else:
                for iEntry,myEntry in enumerate(self.bods):
                    if (myEntry.echoName()==myValue):
                        lFound=True
                        break
        elif (myKey.upper().startswith("LAT")):
            if (myValue.upper()=="ALL"):
                myEntry=[ reg.echoLatticeName() for reg in self.regs if reg.isLattice() ]
                iEntry=[ ii for ii in range(len(self.regs)) if self.regs[ii].isLattice() ]
                lFound=True
            else:
                for iEntry,myEntry in enumerate(self.regs):
                    if (myEntry.echoLatticeName()==myValue):
                        lFound=True
                        break
        elif (myKey.upper().startswith("REG")):
            if (myValue.upper()=="ALL"):
                myEntry=[ reg.echoName() for reg in self.regs ]
                iEntry=[ ii for ii in range(len(self.regs)) ]
                lFound=True
            else:
                for iEntry,myEntry in enumerate(self.regs):
                    if (myEntry.echoName()==myValue):
                        lFound=True
                        break
        elif (myKey.upper().startswith("TRANSFLINKEDTOBODY")):
            if (myValue.upper()=="ALL"):
                myEntry=list(set([ body.retTransformName() for body in self.bods if body.isLinkedToTransform() ])) # unique entries!
                iEntry=[]
                for tEntry in myEntry:
                    mE,iE=self.ret("transf",tEntry)
                    iEntry.append(iE)
                lFound=True
            else:
                mE,iE=self.ret("body",myValue)
                if (mE is not None):
                    if (mE.isLinkedToTransform()):
                        myEntry,iEntry=self.ret("transf",mE.retTransformName())
                        lFound=myEntry is None
                else:
                    print("cannot find body named %s!"%(myValue))
                    exit(1)
        elif (myKey.upper().startswith("TRANSFLINKEDTOLAT")):
            if (myValue.upper()=="ALL"):
                myEntry=list(set([ reg.echoTransformName() for reg in self.regs if reg.isLattice() and reg.isLinkedToTransform() ])) # unique entries!
                iEntry=[]
                for tEntry in myEntry:
                    mE,iE=self.ret("transf",tEntry)
                    iEntry.append(iE)
                lFound=True
            else:
                mE,iE=self.ret("lat",myValue)
                if (mE is not None):
                    if (mE.isLinkedToTransform()):
                        myEntry,iEntry=self.ret("transf",mE.echoTransformName())
                        lFound=myEntry is None
                else:
                    print("cannot find body named %s!"%(myValue))
                    exit(1)
        elif (myKey.upper().startswith("TRANSFLINKEDTOUSRBIN")):
            if (myValue.upper()=="ALL"):
                myEntry=list(set([ mbin.retTransformName() for mbin in self.bins if mbin.isLinkedToTransform() ])) # unique entries!
                iEntry=[]
                for tEntry in myEntry:
                    mE,iE=self.ret("transf",tEntry)
                    iEntry.append(iE)
                lFound=True
            else:
                mE,iE=self.ret("usrbin",myValue)
                if (mE is not None):
                    if (mE.isLinkedToTransform()):
                        myEntry,iEntry=self.ret("transf",mE.retTransformName())
                        lFound=myEntry is None
                else:
                    print("cannot find USRBIN named %s!"%(myValue))
                    exit(1)
        elif (myKey.upper().startswith("TRANSF")):
            if (myValue.upper()=="ALL"):
                myEntry=[ tras.echoName() for tras in self.tras ]
                iEntry=[ ii for ii in range(len(self.tras)) ]
                lFound=True
            else:
                for iEntry,myEntry in enumerate(self.tras):
                    if (myEntry.echoName()==myValue):
                        lFound=True
                        break
        elif (myKey.upper().startswith("BININUNIT") or myKey.upper().startswith("USRBININUNIT")):
            myEntry=[] ; iEntry=[]
            if (isinstance(myValue,float) or isinstance(myValue,int)): myValue=[myValue]
            for ii,myBin in enumerate(self.bins):
                if (abs(myBin.getUnit()) in myValue):
                    myEntry.append(myBin.echoName())
                    iEntry.append(ii)
                    lFound=True
        elif (myKey.upper().startswith("BIN") or myKey.upper().startswith("USRBIN")):
            if (myValue.upper()=="ALL"):
                myEntry=[ myBin.echoName() for myBin in self.bins ]
                iEntry=[ ii for ii in range(len(self.bins)) ]
                lFound=True
            else:
                for iEntry,myEntry in enumerate(self.bins):
                    if (myEntry.echoName()==myValue):
                        lFound=True
                        break
        elif (myKey.upper().startswith("SCO") or myKey.upper().startswith("SCORING")):
            if (myValue.upper()=="ALL"):
                myEntry=[ mySco.echoName() for mySco in self.scos ]
                iEntry=[ ii for ii in range(len(self.scos)) ]
                lFound=True
            else:
                for iEntry,myEntry in enumerate(self.scos):
                    if (myEntry.echoName()==myValue):
                        lFound=True
                        break
        elif (myKey.upper().startswith("USRYIELD")):
            if (myValue.upper()=="ALL"):
                myEntry=[ mySco.echoName() for mySco in self.scos if isinstance(mySco,Usryield) ]
                iEntry=[ ii for ii in range(len(self.scos)) ]
                lFound=True
            else:
                for iEntry,myEntry in enumerate(self.scos):
                    if (myEntry.echoName()==myValue and isinstance(myEntry,Usryield) ):
                        lFound=True
                        break
        elif (myKey.upper().startswith("USRBDX")):
            if (myValue.upper()=="ALL"):
                myEntry=[ mySco.echoName() for mySco in self.scos if isinstance(mySco,Usrbdx) ]
                iEntry=[ ii for ii in range(len(self.scos)) ]
                lFound=True
            else:
                for iEntry,myEntry in enumerate(self.scos):
                    if (myEntry.echoName()==myValue and isinstance(myEntry,Usrbdx) ):
                        lFound=True
                        break
        elif (myKey.upper().startswith("USRTRACK")):
            if (myValue.upper()=="ALL"):
                myEntry=[ mySco.echoName() for mySco in self.scos if isinstance(mySco,Usrtrack) ]
                iEntry=[ ii for ii in range(len(self.scos)) ]
                lFound=True
            else:
                for iEntry,myEntry in enumerate(self.scos):
                    if (myEntry.echoName()==myValue and isinstance(myEntry,Usrtrack) ):
                        lFound=True
                        break
        elif (myKey.upper().startswith("USRCOLL")):
            if (myValue.upper()=="ALL"):
                myEntry=[ mySco.echoName() for mySco in self.scos if isinstance(mySco,Usrcoll) ]
                iEntry=[ ii for ii in range(len(self.scos)) ]
                lFound=True
            else:
                for iEntry,myEntry in enumerate(self.scos):
                    if (myEntry.echoName()==myValue and isinstance(myEntry,Usrcoll) ):
                        lFound=True
                        break
        else:
            print("%s not recognised! What should I look for in the geometry?"%(myKey))
            exit(1)
        if (not lFound):
            myEntry=None
            iEntry=-1
        return myEntry, iEntry

    @staticmethod
    def fromInp(myInpName,iRead=0,newGeom=None):
        '''
        FREE format used only for parsing ROT-DEFI cards (blank space as separator)!
        '''
        if (newGeom is None):
            newGeom=Geometry()
        nBods=len(newGeom.bods)
        nRegs=len(newGeom.regs)
        nBins=len(newGeom.bins)
        nTras=len(newGeom.tras)
        nScos=len(newGeom.scos)
        defineFlags=[]
        print("parsing file %s ..."%(myInpName))
        ff=open(myInpName,'r')
        lFree=False
        lReads=[True]
        lElse=[]
        lBuffReg=iRead==3 # reading a region-only file: empty buffer
        tmpBuf=""
        regBuf=""
        for tmpLine in ff.readlines():

            # PRE-PROCESSOR
            if (tmpLine.startswith("#define")):
                data=tmpLine.split()
                if (len(data)>2):
                    print("...cannot handle define vars with numerical value, only booleans!")
                    print(tmpLine)
                    exit(1)
                if (data[1] not in defineFlags):
                    defineFlags.append(data[1])
                continue
            elif (tmpLine.startswith("#if")):
                data=tmpLine.split()
                lReads.append(data[1] in defineFlags)
                lElse.append(data[1] in defineFlags)
                continue
            elif (tmpLine.startswith("#elif")):
                data=tmpLine.split()
                lReads[-1]=(data[1] in defineFlags)
                lElse[-1]=lElse[-1] or (data[1] in defineFlags)
                continue
            elif (tmpLine.startswith("#else")):
                lReads[-1]=not lElse[-1]
                continue
            elif (tmpLine.startswith("#end")):
                lReads.pop()
                lElse.pop()
                continue
            if (not all(lReads)): continue
            
            # OUTSIDE GEOBEGIN-GEOEND
            if (iRead==0):
                # geometry-related
                if (tmpLine.startswith("GEOBEGIN")):
                    iRead=1
                elif (tmpLine.startswith("ASSIGNMA")):
                    newGeom.assignma(tmpLine)
                    tmpBuf="" # flush buffer
                elif (tmpLine.startswith("ROT-DEFI")):
                    tmpBuf=tmpBuf+tmpLine
                    newGeom.rotdefi(tmpBuf,lFree=lFree)
                    tmpBuf="" # flush buffer
                # scoring-related
                elif (tmpLine.startswith("AUXSCORE")):
                    tmpBuf=tmpBuf+tmpLine
                elif (tmpLine.startswith("ROTPRBIN")):
                    tmpBuf=tmpBuf+tmpLine
                elif (tmpLine.startswith("USRBIN")):
                    tmpBuf=tmpBuf+tmpLine
                    if(tmpLine.strip().endswith("&")):
                       newGeom.add(Usrbin.fromBuf(tmpBuf.strip()),what="BIN")
                       tmpBuf="" # flush buffer
                elif (tmpLine.startswith("USRYIELD")):
                    tmpBuf=tmpBuf+tmpLine
                    if(tmpLine.strip().endswith("&")):
                       newGeom.add(Usryield.fromBuf(tmpBuf.strip()),what="SCO")
                       tmpBuf="" # flush buffer
                elif (tmpLine.startswith("USRBDX")):
                    tmpBuf=tmpBuf+tmpLine
                    if(tmpLine.strip().endswith("&")):
                       newGeom.add(Usrbdx.fromBuf(tmpBuf.strip()),what="SCO")
                       tmpBuf="" # flush buffer
                elif (tmpLine.startswith("USRTRACK")):
                    tmpBuf=tmpBuf+tmpLine
                    if(tmpLine.strip().endswith("&")):
                       newGeom.add(Usrtrack.fromBuf(tmpBuf.strip()),what="SCO")
                       tmpBuf="" # flush buffer
                elif (tmpLine.startswith("USRCOLL")):
                    tmpBuf=tmpBuf+tmpLine
                    if(tmpLine.strip().endswith("&")):
                       newGeom.add(Usrcoll.fromBuf(tmpBuf.strip()),what="SCO")
                       tmpBuf="" # flush buffer
                # comment line
                elif (tmpLine.startswith("*")):
                    tmpBuf=tmpBuf+tmpLine
                # format-related
                elif (tmpLine.startswith("FREE")):
                    lFree=True
                elif (tmpLine.startswith("FIXED")):
                    lFree=False
                # other
                else:
                    # another card, to be skipped
                    tmpBuf="" # flush buffer
                    
            # INSIDE GEOBEGIN-GEOEND
            elif (iRead==1):
                # title after GEOBEGIN
                newGeom.title=tmpLine[20:].strip()
                iRead=2
                tmpBuf="" # flush buffer
            elif (iRead==2):
                # definition of FLUKA bodies
                if (tmpLine.startswith("END")):
                    iRead=3
                    tmpBuf="" # flush buffer
                elif (tmpLine.startswith("$start")):
                    print("$start* cards NOT supported!")
                    exit(1)
                else:
                    tmpBuf=tmpBuf+tmpLine
                    if (not tmpLine.startswith("*")):
                        # acquire body
                        newGeom.add(Body.fromBuf(tmpBuf.strip()),what="BODY")
                        tmpBuf="" # flush buffer
            elif (iRead==3):
                # definition of FLUKA regions
                if (tmpLine.startswith("END")):
                    if (len(regBuf)>0):
                        # acquire region
                        newGeom.add(Region.fromBuf(regBuf),what="reg")
                        regBuf="" # flush region def buffer
                    tmpBuf="" # flush buffer
                    iRead=4
                else:
                    if (tmpLine.startswith("*")):
                        # comment line: store in buffer
                        tmpBuf=tmpBuf+tmpLine
                        continue
                    if (tmpLine.startswith(" ")):
                        # region definition continues
                        regBuf=regBuf+tmpBuf+tmpLine
                        tmpBuf="" # flush buffer
                    else:
                        # a new region
                        if (len(regBuf)>0):
                            # acquire region previously read (if any)
                            newGeom.add(Region.fromBuf(regBuf),what="reg")
                            regBuf="" # flush region def buffer
                        regBuf=tmpBuf+tmpLine
                        tmpBuf="" # flush buffer
                    
            elif (iRead==4):
                # LATTICE cards
                if (tmpLine.startswith("GEOEND")):
                    tmpBuf="" # flush buffer
                    iRead=0
                elif (tmpLine.startswith("LATTICE")):
                    # acquire card
                    newGeom.lattice(tmpLine)
                continue
                    
        ff.close()
        if (lBuffReg and iRead==3 and len(regBuf)>0):
            # acquire region
            newGeom.add(Region.fromBuf(regBuf),what="reg")
            regBuf="" # flush region def buffer
            tmpBuf="" # flush buffer
            iRead=0
        if (len(newGeom.bods)-nBods>0):
            print("...acquired %d bodies;"%(len(newGeom.bods)-nBods))
        if (len(newGeom.regs)-nRegs>0):
            print("...acquired %d regions;"%(len(newGeom.regs)-nRegs))
        if (len(newGeom.bins)-nBins>0):
            print("...acquired %d USRBIN(s);"%(len(newGeom.bins)-nBins))
        if (len(newGeom.scos)-nScos>0):
            print("...acquired %d region-based scoring(s);"%(len(newGeom.scos)-nScos))
        if (len(newGeom.tras)-nTras>0):
            print("...acquired %d transformation(s);"%(len(newGeom.tras)-nTras))
        print("...done;")
        return newGeom

    @staticmethod
    def appendGeometries(myGeos,myTitle=None):
        '''
        Barely appending geometries one to another;
        '''
        new=deepcopy(myGeos[0])
        for myGeo in myGeos[1:]:
            new.bods=new.bods+myGeo.bods
            new.regs=new.regs+myGeo.regs
            for ii,myTras in enumerate(myGeo.tras,1):
                myTras.ID=ii+len(new.tras)
            new.tras=new.tras+myGeo.tras
            new.bins=new.bins+myGeo.bins
            new.scos=new.scos+myGeo.scos
        if (myTitle is None):
            myTitle="appended geometries"
        new.title=myTitle
        return new

    def echo(self,oFileName,lSplit=False,what="all",dMode="w"):
        '''
        - what="all"/"bodies"/"regions"/"materials"/"transformation"/"bins"/"scos"
        In case oFileName ends with ".geo", lSplit is activated,
           overriding the user request, and bodies/regions are
           dumped in the .geo file, whereas assignmat cards are
           dumped in the _assignmat.inp file.
        '''
        import os
        
        if (not oFileName.endswith(".inp") and not oFileName.endswith(".geo")):
            oFileName=oFileName+".inp"
        if (oFileName.endswith(".geo")):
            lSplit=True

        if (what.upper().startswith("BOD")):
            print("saving bodies in file %s ..."%(oFileName))
            ff=open(oFileName,dMode)
            ff.write("* \n")
            for tmpBody in self.bods:
                ff.write("%s\n"%(tmpBody.echo()))
            ff.write("* \n")
            ff.close()
            print("...done;")
        elif (what.upper().startswith("REG")):
            print("saving regions in file %s ..."%(oFileName))
            ff=open(oFileName,dMode)
            ff.write("* \n")
            for tmpReg in self.regs:
                ff.write("%s\n"%(tmpReg.echo()))
            ff.write("* \n")
            ff.close()
            print("...done;")
        elif (what.upper().startswith("LAT")):
            LatNames,iLat=self.ret("LAT","ALL")
            if (len(LatNames)>0):
                print("saving LATTICE cards in file %s ..."%(oFileName))
                ff=open(oFileName,dMode)
                ff.write("* \n")
                for tmpReg in self.regs:
                    if (tmpReg.isLattice()):
                        ff.write("%s\n"%(tmpReg.echo(lLat=True)))
                ff.write("* \n")
                ff.close()
                print("...done;")
        elif (what.upper().startswith("TRANSF")):
            print("saving ROT-DEFI cards in file %s ..."%(oFileName))
            ff=open(oFileName,dMode)
            ff.write("* \n")
            ff.write("FREE \n")
            for tmpTrasf in self.tras:
                ff.write("%s\n"%(tmpTrasf.echo())) # FREE format by default
            ff.write("FIXED \n")
            ff.write("* \n")
            ff.close()
            print("...done;")
        elif (what.upper().startswith("MAT")):
            print("saving ASSIGNMA cards in file %s ..."%(oFileName))
            ff=open(oFileName,dMode)
            ff.write("* \n")
            for tmpReg in self.regs:
                ff.write("%s\n"%(tmpReg.echo(lMat=True)))
            ff.write("* \n")
            ff.close()
            print("...done;")
        elif (what.upper().startswith("BIN")):
            print("saving USRBINs in file %s ..."%(oFileName))
            ff=open(oFileName,dMode)
            ff.write("* \n")
            for tmpBin in self.bins:
                ff.write("%s\n"%(tmpBin.echo()))
            ff.write("* \n")
            ff.close()
            print("...done;")
        elif (what.upper().startswith("SCO")):
            print("saving region-based scorings in file %s ..."%(oFileName))
            ff=open(oFileName,dMode)
            ff.write("* \n")
            for tmpSco in self.scos:
                ff.write("%s\n"%(tmpSco.echo()))
            ff.write("* \n")
            ff.close()
            print("...done;")
        elif (what.upper()=="ALL"):
            if (lSplit):
                if (oFileName.endswith(".inp")):
                    # split geometry definition into bodies,
                    #   regions, assignmat, rotdefi and usrbin files,
                    #   to be used with pure #include statements;
                    self.echo(oFileName.replace(".inp","_bodies.inp",1),\
                              lSplit=False,what="bodies",dMode="w")
                    self.echo(oFileName.replace(".inp","_regions.inp",1),\
                              lSplit=False,what="regions",dMode="w")
                    self.echo(oFileName.replace(".inp","_lattices.inp",1),\
                              lSplit=False,what="lattices",dMode="w")
                    self.echo(oFileName.replace(".inp","_assignmats.inp",1),\
                              lSplit=False,what="materials",dMode="w")
                    if (len(self.tras)>0):
                        self.echo(oFileName.replace(".inp","_rotdefis.inp",1),\
                              lSplit=False,what="transf",dMode="w")
                    if (len(self.bins)>0):
                        self.echo(oFileName.replace(".inp","_scorings.inp",1),\
                              lSplit=False,what="bin",dMode="w")
                    if (len(self.scos)>0):
                        dMode="w"
                        if (len(self.bins)>0): dMode="a"
                        self.echo(oFileName.replace(".inp","_scorings.inp",1),\
                              lSplit=False,what="sco",dMode=dMode)
                else:
                    # split geometry definition into a .geo file
                    #   and an assignmat, rotdefi and usrbin files;
                    #   the former is encapsulated between GEOBEGIN and GEOEND cards,
                    #   the other is imported via an #include statement
                    ff=open(oFileName,"w")
                    ff.write("% 5d% 5d%10s%s\n"%(0,0,"",self.title))
                    ff.close()
                    self.echo(oFileName,lSplit=False,what="bodies",dMode="a")
                    ff=open(oFileName,"a")
                    ff.write("%-10s\n"%("END"))
                    ff.close()
                    self.echo(oFileName,lSplit=False,what="regions",dMode="a")
                    ff=open(oFileName,"a")
                    ff.write("%-10s\n"%("END"))
                    ff.close()
                    self.echo(oFileName,lSplit=False,what="lattices",dMode="a")
                    self.echo(oFileName.replace(".geo","_assignmats.inp",1),\
                              lSplit=False,what="materials",dMode="w")
                    if (len(self.tras)>0):
                        self.echo(oFileName.replace(".geo","_rotdefis.inp",1),\
                              lSplit=False,what="transf",dMode="w")
                    if (len(self.bins)>0):
                        self.echo(oFileName.replace(".geo","_scorings.inp",1),\
                              lSplit=False,what="bin",dMode="w")
                    if (len(self.scos)>0):
                        dMode="w"
                        if (len(self.bins)>0): dMode="a"
                        self.echo(oFileName.replace(".geo","_scorings.inp",1),\
                              lSplit=False,what="sco",dMode=dMode)
            else:
                ff=open(oFileName,"w")
                ff.write("%-10s%60s%-10s\n"%("GEOBEGIN","","COMBNAME"))
                ff.write("% 5d% 5d%10s%s\n"%(0,0,"",self.title))
                ff.close()
                self.echo(oFileName,lSplit=False,what="bodies",dMode="a")
                ff=open(oFileName,"a")
                ff.write("%-10s\n"%("END"))
                ff.close()
                self.echo(oFileName,lSplit=False,what="regions",dMode="a")
                ff=open(oFileName,"a")
                ff.write("%-10s\n"%("END"))
                ff.close()
                self.echo(oFileName,lSplit=False,what="lattices",dMode="a")
                ff=open(oFileName,"a")
                ff.write("%-10s\n"%("GEOEND"))
                ff.close()
                if (len(self.tras)>0):
                    self.echo(oFileName,lSplit=False,what="transf",dMode="a")
                self.echo(oFileName,lSplit=False,what="materials",dMode="a")
                if (len(self.bins)>0):
                    self.echo(oFileName,lSplit=False,what="bin",dMode="a")
                if (len(self.scos)>0):
                    self.echo(oFileName,lSplit=False,what="sco",dMode="a")
        else:
            print("...what should I echo? %s NOT reconised!"%(what))

    @staticmethod
    def ActualCopy(myGeo,lTrigScoring=True,new=None):
        if (new is None): new=Geometry()
        new.bods=deepcopy(myGeo.bods)
        new.regs=deepcopy(myGeo.regs)
        myTras=deepcopy(myGeo.tras)
        if (lTrigScoring):
            new.bins=deepcopy(myGeo.bins)
            new.scos=deepcopy(myGeo.scos)
        else:
            # do not copy USRBINs and remove uselss transformations
            allTrasfNames,iEntry=myGeo.ret("TRANSF","ALL")
            bodTrasfNames,iEntry=myGeo.ret("TRANSFLINKEDTOBODY","ALL")
            for iT,myT in reversed(list(enumerate(allTrasfNames))):
                if (myT not in bodTrasfNames):
                    myTras.pop(iT)
        if (len(myTras)>0): new.tras=myTras
        new.title=myGeo.title
        return new

    @staticmethod
    def LatticeCopy(myGeo,lTrigScoring=True,RegName=None,LatName=None,LatMat="VACUUM",new=None):
        '''
        The full geometry is copied in a single LATTICE region, no support
            for any OUTER region is provided, for the time being.
        '''
        if (RegName is None): RegName="LATREG"
        if (LatName is None): LatName=RegName
        if (new is None): new=Geometry()
        myReg=Region(myName=RegName)
        myReg.assignLat(myLatName=LatName)
        myReg.material=LatMat
        new.add(myReg,what="REG")
        myTras=deepcopy(myGeo.tras)
        if (lTrigScoring):
            new.bins=deepcopy(myGeo.bins)
            new.scos=deepcopy(myGeo.scos)
        else:
            # do not copy USRBINs and remove uselss transformations
            allTrasfNames,iEntry=myGeo.ret("TRANSF","ALL")
            binTrasfNames,iEntry=myGeo.ret("TRANSFLINKEDTOUSRBIN","ALL")
            for iT,myT in reversed(list(enumerate(allTrasfNames))):
                if (myT in binTrasfNames):
                    myTras.pop(iT)
        if (len(myTras)>0): new.tras=myTras
        new.title="LATTICE of %s"%(myGeo.title)
        return new

    def solidTrasform(self,dd=None,myMat=None,myTheta=None,myAxis=3,lDegs=True,lGeoDirs=False,lOnlyGeo=False,lWrapGeo=False,myName="ToFinPos",myComment=None,lDebug=False):
        '''
        Bodies are applied the transformation as requested by the user:
        * first, rotation (meant to be expressed in ref sys of the object to rotate);
        * second, translation.

        ROT-DEFI cards express the opposite transformation (it is used runtime
          in particle tracking, so it is used to track particles in the original
          position). In addition, in ROT-DEFI cards:
        * the translation is applied first, then the rotation;
        * the rotation angles (azimuth) have opposite sign wrt a rotation angle
          in a right-handed system.

        Booleans:
        * lGeoDirs: if true, the transformation is applied to bodies not by modifying their
                      definitions, but via a $start_transform geometry directive:
                    - in case the body is already subject to a $start_transform geometry directive,
                      the current transformation is added to its transformation;
                    - in case the body is NOT subject to a $start_transform geometry directive,
                      the current transformation is added to the existing list of transformations
                      and the body linked to it;
                    if false, the transformation is applied to bodies by modifying their definitions;
        * lOnlyGeo: if true, the current transformation is applied only to bodies and to transformations
                      linked to LATTICE regions; if false, the current transformation is applied also
                      to the USRBIN cards;
        * lWrapGeo: if true, the current transformation is wrapped around existing transformations
                      for LATTICE regions; this is necessary when the PROTOTYPE of a LATTICE
                      region is already part of the gridded geometry, and the gridded is being moved;
        '''
        print("applying solid transformation(s)...")
        if (myMat is None and myTheta is None and dd is None):
            print("...no transformation provided!")
        else:
            ROTDEFIlist=[]; ROTDEFIlistINV=[];
            if (myMat is not None):
                print("...applying transformation expressed by matrix to geometry...")
                if (not lGeoDirs):
                    for myBod in self.bods:
                        myBod.rotate(myMat=myMat,myTheta=None,myAxis=None,lDegs=lDegs,lDebug=lDebug)
                thetas=myMat.GetGimbalAngles() # [degs]
                for myAx,myTh in enumerate(thetas,1):
                    if (myTh!=0.0):
                        ROTDEFIlist.append(RotDefi(myAx=myAx,myTh=myTh))
                        if (lWrapGeo): ROTDEFIlistINV.append(RotDefi(myAx=myAx,myTh=-myTh))
            elif (myTheta is not None):
                if (isinstance(myTheta,list) and isinstance(myAxis,list)):
                    if ( len(myTheta)!=len(myAxis) ):
                        print("...inconsistent number of angles (%d) and axes (%d)!"\
                              %(len(myTheta),len(myAxis)))
                        exit(1)
                    for myT,myAx in zip(myTheta,myAxis):
                        # iteratively call this same method, on a single angle
                        self.solidTrasform(myTheta=myT,myAxis=myAx,lDegs=lDegs,lGeoDirs=lGeoDirs,\
                                           lOnlyGeo=lOnlyGeo,lWrapGeo=lWrapGeo,lDebug=lDebug)
                elif (myTheta!=0.0):
                    print("...applying rotation by %f degs around axis %d..."%\
                          (myTheta,myAxis))
                    if (not lGeoDirs):
                        myMat=RotMat(myAng=myTheta,myAxis=myAxis,lDegs=lDegs,lDebug=lDebug)
                        for myBod in self.bods:
                            myBod.rotate(myMat=myMat,myTheta=None,myAxis=None,lDegs=lDegs,lDebug=lDebug)
                    ROTDEFIlist.append(RotDefi(myAx=myAxis,myTh=myTheta))
                    if (lWrapGeo): ROTDEFIlistINV.append(RotDefi(myAx=myAxis,myTh=-myTheta))
            if (dd is not None):
                print("...applying traslation array [%f,%f,%f] cm..."%\
                      (dd[0],dd[1],dd[2]))
                if (not lGeoDirs):
                    for myBod in self.bods:
                        myBod.traslate(dd=dd,lDebug=lDebug)
                myDD=dd
                if (isinstance(myDD,list)):
                    myDD=np.array(dd)
                ROTDEFIlist.append(RotDefi(myDD=-myDD))
                if (lWrapGeo): ROTDEFIlistINV.append(RotDefi(myDD=myDD))
            if (len(ROTDEFIlist)>0):
                if (lDebug):
                    print("...final list of ROT-DEFI cards (as in memory):")
                    for tmpRotDefi in ROTDEFIlist:
                        print(tmpRotDefi.echo(myID=1,myName="ignore_myName_myIndex"))
                # add transformation:

                # bodies
                if (lGeoDirs):
                    lCreate=False; Tname="%s_bdy"%(myName); tTrasfs=[]
                    for myBod in self.bods:
                        if (myBod.isLinkedToTransform()):
                            myTname=myBod.retTransformName()
                            if (myTname not in tTrasfs): tTrasfs.append(myTname)
                        else:
                            myBod.linkTransformName(Tname=Tname)
                            if (not lCreate): lCreate=True
                    # current transformation alone
                    if (lCreate):
                        myEntry,iEntry=self.ret("TRANSF",Tname)
                        if (myEntry is None):
                            tTrasfs.append(Tname)
                            print("...adding the transformation %s to (existing) list of transformations - Bodies part..."%(Tname))
                            self.add(Transformation(myID=len(self.tras)+1,myName=Tname),what="tras")
                    # append current transformation to existing ones
                    for myTrasName in tTrasfs:
                        if (lDebug): print("...updating BODY %s ROT-DEFI cards..."%(myTrasName))
                        myTras,iEntry=self.ret("transf",myTrasName)
                        myTras.AddRotDefis(deepcopy(ROTDEFIlist),iAdd=0)
                    # add comment, in case
                    if (lCreate and myComment is not None):
                        myEntry,iEntry=self.ret("TRANSF",Tname)
                        myEntry.headMe(myComment)
                
                # LATTICEs
                lCreate=False; Tname="%s_lat"%(myName); tTrasfs=[]
                for myReg in self.regs:
                    if myReg.isLattice():
                        if (myReg.isLinkedToTransform()):
                            myTname=myReg.echoTransformName()
                            if (myTname not in tTrasfs): tTrasfs.append(myTname)
                        else:
                            myReg.assignTrasf(myTrasfName=Tname)
                            if (not lCreate): lCreate=True
                # current transformation alone
                if (lCreate):
                    myEntry,iEntry=self.ret("TRANSF",Tname)
                    if (myEntry is None):
                        tTrasfs.append(Tname)
                        print("...adding the transformation %s to (existing) list of transformations - LATTICE part..."%(Tname))
                        self.add(Transformation(myID=len(self.tras)+1,myName=Tname),what="tras")
                # append current transformation to existing ones
                for myTrasName in tTrasfs:
                    if (lDebug): print("...updating LATTICE %s ROT-DEFI cards..."%(myTrasName))
                    myTras,iEntry=self.ret("transf",myTrasName)
                    myTras.AddRotDefis(deepcopy(ROTDEFIlist),iAdd=0)
                    if (lWrapGeo):
                        if (lDebug): print("    ...wrapped!")
                        myTras.AddRotDefis(reversed(deepcopy(ROTDEFIlistINV)),iAdd=-1)
                # add comment, in case
                if (lCreate and myComment is not None):
                    myEntry,iEntry=self.ret("TRANSF",Tname)
                    myEntry.headMe(myComment)
                
                # USRBIN part
                if (not lOnlyGeo):
                    lCreate=False; Tname="%s_bin"%(myName); tTrasfs=[]
                    lTraslOnly=(dd is not None and myMat is None and myTheta is None)
                    for myBin in self.bins:
                        if (lDebug): print("BEFORE moving:"); print(myBin.echo())
                        if (lTraslOnly and not myBin.isLinkedToTransform() ):
                            myBin.move(dd,axes=["X","Y","Z"],lAbs=False)
                        elif ( myBin.isLinkedToTransform() ):
                            myTname=myBin.retTransformName()
                            if (myTname not in tTrasfs): tTrasfs.append(myTname)
                        else:
                            myBin.assignTransformName(Tname)
                            if (not lCreate): lCreate=True
                        if (lDebug): print("AFTER moving:"); print(myBin.echo())
                    # current transformation alone
                    if (lCreate):
                        myEntry,iEntry=self.ret("TRANSF",Tname)
                        if (myEntry is None):
                            tTrasfs.append(Tname)
                            print("...adding the transformation %s to (existing) list of transformations - USRBIN part..."%(Tname))
                            self.add(Transformation(myID=len(self.tras)+1,myName=Tname),what="tras")
                    # append current transformation to existing ones
                    for myTrasName in tTrasfs:
                        if (lDebug): print("...updating USRBIN %s ROT-DEFI cards..."%(myTrasName))
                        myTras,iEntry=self.ret("transf",myTrasName)
                        myTras.AddRotDefis(deepcopy(ROTDEFIlist),iAdd=0)
                    # add comment, in case
                    if (lCreate and myComment is not None):
                        myEntry,iEntry=self.ret("TRANSF",Tname)
                        myEntry.headMe(myComment)
                    
        print("...done.")

    def rename(self,newName,lNotify=True,nDigits=2,addChar="_",exceptions=None):
        print("renaming geometry...")
        nName,nNameFmt=TailNameInt(newName,nDigits=nDigits,addChar=addChar)
        nNameSco,nNameScoFmt=TailNameInt(newName,maxLen=10,nDigits=nDigits+1,addChar=addChar)
        oldBodyNames=[]; newBodyNames=[]
        oldRegNames=[] ; newRegNames=[]
        oldTrasNames=[]; newTrasNames=[]
        for iBody,myBod in enumerate(self.bods):
            myCurrName=myBod.echoName()
            if (exceptions is not None):
                if ( "bods" in exceptions ):
                    if (myCurrName in exceptions["bods"]):
                        continue
            oldBodyNames.append(myCurrName)
            newBodyNames.append(nNameFmt%(iBody+1))
            myBod.rename(newBodyNames[-1],lNotify=lNotify)
        for iReg,myReg in enumerate(self.regs):
            myCurrName=myReg.echoName()
            if (exceptions is not None):
                if ( "regs" in exceptions ):
                    if (myCurrName in exceptions["regs"]):
                        continue
            oldRegNames.append(myCurrName)
            newRegNames.append(nNameFmt%(iReg+1))
            myReg.rename(newRegNames[-1],lNotify=lNotify)
            if (myReg.isLattice()):
                myReg.assignLat(myLatName=newRegNames[-1])
            myReg.BodyNameReplaceInDef(oldBodyNames,newBodyNames)
        for iTras,myTras in enumerate(self.tras):
            myCurrName=myTras.echoName()
            if (exceptions is not None):
                if ( "tras" in exceptions ):
                    if (myCurrName in exceptions["tras"]):
                        continue
            oldTrasNames.append(myCurrName)
            newTrasNames.append(nNameFmt%(iTras+1))
            myTras.rename(newTrasNames[-1],lNotify=lNotify)
        for iBin,myBin in enumerate(self.bins):
            if (myBin.isLinkedToTransform()):
                trName=myBin.retTransformName()
                lFound=False
                for oldTrasName,newTrasName in zip(oldTrasNames,newTrasNames):
                    if (trName==oldTrasName):
                        myBin.assignTransformName(newTrasName)
                        lFound=True
                        break
                if (not lFound):
                    print("cannot find transformation named %s!"%(trName))
                    exit(1)
            else:
                print("Geometry.rename(): USRBIN %s with no associated transformation..."%(myBin.echoName()))
            myCurrName=myBin.echoName()
            if (exceptions is not None):
                if ( "bins" in exceptions ):
                    if (myCurrName in exceptions["bins"]):
                        continue
            myBin.rename(nNameScoFmt%(iBin+1),lNotify=lNotify)
        for iSco,mySco in enumerate(self.scos):
            for oName,nName in zip(oldRegNames,newRegNames):
                mySco.regNameReplaceInDef(oName,nName)
            myCurrName=mySco.echoName()
            if (exceptions is not None):
                if ( "scos" in exceptions ):
                    if (myCurrName in exceptions["scos"]):
                        continue
            mySco.rename(nNameScoFmt%(iSco+1),lNotify=lNotify)
        for myBod in self.bods:
            if (myBod.isLinkedToTransform()):
                if (myBod.retTransformName() not in oldTrasNames):
                    print("cannot find name of transformation for moving body:")
                    print(myBod.echo())
                    exit(1)
                ii=oldTrasNames.index(myBod.retTransformName())
                myBod.linkTransformName(Tname=newTrasNames[ii])
        for myReg in self.regs:
            if (myReg.isLattice()):
                if (myReg.echoTransformName() not in oldTrasNames):
                    print("cannot find name of transformation for moving LATTICE region:")
                    print(myReg.echo())
                    exit(1)
                ii=oldTrasNames.index(myReg.echoTransformName())
                myReg.assignTrasf(myTrasfName=newTrasNames[ii])
        print("...done.")

    def flagRegs(self,whichRegs,rCont,rCent=np.zeros(3)):
        if (isinstance(whichRegs,str)):
            if (whichRegs.upper()=="ALL"):
                regs2mod,iRegs2mod=self.ret("reg","ALL")
            else:
                regs2mod=[whichRegs]
        else:
            if ( "ALL" in [tmpStr.upper() for tmpStr in whichRegs] ):
                regs2mod,iRegs2mod=self.ret("reg","ALL")
            else:
                regs2mod=whichRegs
        for whichReg in regs2mod:
            outReg,iReg=self.ret("reg",whichReg)
            outReg.initCont(rCont=rCont,rCent=rCent)

    def resizeBodies(self,newL,whichBods="ALL",lDebug=False):
        '''
        input:
        - newL: new length [cm];
        - whichBods: list of body names to be updated (if infinite);
        '''
        if (isinstance(whichBods,str)):
            if (whichBods.upper()=="ALL"):
                bods2mod,iBods2mod=self.ret("bod","ALL")
                if (not isinstance(bods2mod,list)):
                    bods2mod, iBods2mod = [whichBods], [iBods2mod]
            else:
                bods2mod=[whichBods]
        else:
            if ( "ALL" in [tmpStr.upper() for tmpStr in whichBods] ):
                bods2mod,iBods2mod=self.ret("bod","ALL")
            else:
                bods2mod=whichBods
        if (lDebug): print("re-sizing %d bodies..."%(len(bods2mod)))
        for bod2mod in bods2mod:
            whichBod,iBod=self.ret("bod",bod2mod)
            whichBod.resize(newL,lDebug=lDebug)
        if (lDebug): print("...done;")

    def makeBodiesRotatable(self,lDebug=False,infL=1000.):
        for myBod in self.bods:
            myBod.makeRotatable(lDebug=lDebug,infL=infL)

    def makeBodiesUNrotatable(self,lDebug=False,infL=1000.):
        for myBod in self.bods:
            myBod.makeUNrotatable(lDebug=lDebug,infL=infL)

    def reAssiginUSRBINunits(self,nMaxBins=None,nUSRBINs=None,usedUnits=None,lDebug=False):
        if (lDebug): print("re-assigning USRBIN units...")
        if (nMaxBins is not None and nUSRBINs is not None):
            print("Please tell me if I have to re-assign USRBIN units based on:")
            print("- max number of bins in a unit;")
            print("- max number of USRBINs in a unit;")
            exit(1)
        if (usedUnits is None): usedUnits=[]
        if (type(usedUnits) is not list): usedUnits=[usedUnits]
        uniqueUnits=list(set([ myBin.getUnit() for myBin in self.bins ]))
        uniqueUnits.sort(key=abs)
        if (lDebug):
            print("...%d original units:"%(len(uniqueUnits)),uniqueUnits)
            if (len(usedUnits)>0):
                print("...units NOT to be used:",usedUnits)
        currUnits=[21+ii for ii in range(len(uniqueUnits))]
        for ii in range(len(currUnits)):
            while (currUnits[ii] in [abs(iu) for iu in usedUnits]):
                currUnits[ii]=currUnits[ii]+1
                if (currUnits[ii]>99):
                    print("...exceeding max number of supported units!")
                    exit(1)
        myN=[ 0 for ii in range(len(currUnits)) ]
        if (nMaxBins is not None):
            nMax=nMaxBins
        elif(nUSRBINs is not None):
            nMax=nUSRBINs
        else:
            print("Please tell me if I have to re-assign USRBIN units based on:")
            print("- max number of bins in a unit;")
            print("- max number of USRBINs in a unit;")
            exit(1)
        if (isinstance(nMax,int) or isinstance(nMax,float)):
            nMax=[nMax for ii in range(len(uniqueUnits))]
        newUnits=[ [currUnits[ii]] for ii in range(len(uniqueUnits)) ]
        for myBin in self.bins:
            iUnit=uniqueUnits.index(myBin.getUnit())
            if (nMaxBins is not None):
                nAdd=myBin.getNbins()
            elif(nUSRBINs is not None):
                nAdd=1
            if (myN[iUnit]+nAdd>nMax[iUnit]):
                myUnit=currUnits[iUnit]
                while(myUnit<=max(currUnits) or \
                      myUnit in usedUnits ):
                    myUnit=myUnit+1
                    if (myUnit>99):
                        print("...exceeding max number of supported units!")
                        exit(1)
                currUnits[iUnit]=myUnit
                myN[iUnit]=nAdd
                newUnits[iUnit].append(myUnit)
            else:
                myN[iUnit]=myN[iUnit]+nAdd
            myBin.setUnit(currUnits[iUnit])
        for iUnit in range(len(uniqueUnits)):
            print("...old unit: %d - new units:"%(uniqueUnits[iUnit]),newUnits[iUnit])
        if (lDebug): print("...done;")

    def resizeUsrbins(self,newL,whichBins=None,axis=3,lDebug=False):
        '''
        input:
        - newL: new length [cm];
        - whichBins: unit(s)/name(s) of USRBINs to be updated;
        '''
        if (lDebug): print("resizing USRBINs...")
        if (whichBins is None): whichBins="ALL"
        if (isinstance(whichBins,str)):
            if (whichBins.upper()=="ALL"):
                bins2mod,iBins2mod=self.ret("bin","ALL") # returns a list of names and a list of scalars
                if (lDebug): print("...re-sizing ALL USRBINs, i.e. %d ..."%(len(bins2mod)))
            else:
                bins2mod=[whichBins]
        elif (isinstance(whichBins,float) or isinstance(whichBins,int)):
            bins2mod,iBins2mod=self.ret("BININUNIT",whichBins) # returns a list of names and a list of scalars
            if (lDebug): print("re-sizing USRBINs in unit %d, i.e. %d ..."%(whichBins,len(bins2mod)))
        elif (isinstance(whichBins,list)):
            bins2mod=[]; iBins2mod=[]
            for whichBin in whichBins:
                if (isinstance(whichBin,float) or isinstance(whichBin,int)):
                    tBins2mod,tIBins2mod=self.ret("BININUNIT",whichBin)
                    print("re-sizing USRBINs in unit %d, i.e. %d ..."%(whichBin,len(tBins2mod)))
                    if (isinstance(tBins2mod,list)):
                        bins2mod=bins2mod+tBins2mod
                    else:
                        bins2mod.append(tBins2mod)
                elif (isinstance(whichBin,str)):
                    print("re-sizing %s USRBIN..."%(whichBin))
                    bins2mod.append(whichBin)
        else:
            print("Geometry.resizeUsrbins(): Wrong indication of USRBINs for resizing!")
            print(whichBins)
            exit(1)
        if (bins2mod is not None):
            for bin2mod in bins2mod:
                whichBin,iBin=self.ret("bin",bin2mod)
                whichBin.resize(newL,axis=3)
                if (lDebug): print(whichBin.echo())
        if (lDebug): print("...done;")

    def moveUsrbins(self,myCoord,axes=3,whichBins=None,lAbs=True,lDebug=False):
        if (lDebug): print("moving USRBINs by",myCoord,"along axes",axes)
        if (whichBins is None): whichBins="ALL"
        if (isinstance(whichBins,str)):
            if (whichBins.upper()=="ALL"):
                bins2mod,iBins2mod=self.ret("bin","ALL")
                if (lDebug): print("...moving ALL USRBINs, i.e. %d ..."%(len(bins2mod)))
            else:
                print("Geometry.moveUsrbins(): Cannot specify USRBIN names for moving!")
                exit(1)
        elif (isinstance(whichBins,list)):
            bins2mod=[]; iBins2mod=[]
            for whichBin in whichBins:
                tBins2mod,tIBins2mod=self.ret("BIN",whichBin)
                if (tBins2mod is None):
                    print("Geometry.moveUsrbins(): Cannot find USRBIN named %s!"%(whichBin))
                    exit(1)
                if (isinstance(tBins2mod,list)):
                    bins2mod=bins2mod+tBins2mod
                    iBins2mod=iBins2mod+tIBins2mod
                    print("moving %d USRBINs named %s ..."%(len(tBins2mod),whichBin))
                else:
                    bins2mod.append(tBins2mod)
                    iBins2mod.append(tIBins2mod)
                    print("moving USRBIN named %s ..."%(whichBin))
        else:
            print("Geometry.moveUsrbins(): Wrong indication of USRBINs for moving!")
            print(whichBins)
            exit(1)
        if (bins2mod is not None):
            for bin2mod in bins2mod:
                bin2mod.move(myCoord,axes=axes,lAbs=lAbs)
                if (lDebug): print(bin2mod.echo())
        if (lDebug): print("...done;")
        
    def checkTransformations(self):
        '''
        Check that ROT-DEFI cards serve either only $start_transform directives,
           or only LATTICE regions or USRBIN cards;
        '''
        print("checking that every ROT-DEFI serve either only $start_transform directives,")
        print("   or only LATTICE regions or USRBIN card...")
        bodTrasfNames,iEntry=self.ret("TRANSFLINKEDTOBODY","ALL")
        latTrasfNames,iEntry=self.ret("TRANSFLINKEDTOLAT","ALL")
        binTrasfNames,iEntry=self.ret("TRANSFLINKEDTOUSRBIN","ALL")
        lShared=False
        for bodTrasfName in bodTrasfNames:
            if (bodTrasfName in latTrasfNames):
                print("...ROT-DEFI %s used for both $start_transform directives and LATTICE regions!"%(bodTrasfName))
                lShared=True
        for latTrasfName in latTrasfNames:
            if (latTrasfName in binTrasfNames):
                print("...ROT-DEFI %s used for both LATTICE regions and USRBIN scoring cards!"%(latTrasfName))
                lShared=True
        for binTrasfName in binTrasfNames:
            if (binTrasfName in bodTrasfNames):
                print("...ROT-DEFI %s used for both USRBIN scoring cards and $start_transform directives!"%(binTrasfName))
                lShared=True
        print("...done.")
        return lShared

    @staticmethod
    def DefineHive_SphericalShell(Rmin,Rmax,NR,Tmin,Tmax,NT,Pmin,Pmax,NP,defMat="VACUUM",tmpTitle="Hive for a spherical shell",lWrapBHaround=False,whichMaxLen=None,lDebug=True):
        '''
        This method defines the hive for a grid on a spherical shell.

        The grid is described in spherical coordinates:
        - r [cm];
        - theta [degs]: angle in yz-plane (positive when pointing towards y>0);
        - phi [degs]: angle in xz-plane (positive when pointing towards x>0).
        The grid is centred around the z-axis.

        NR, NT, NP are number of points (cell centers) along r, theta and phi
          in the grid; therefore, the number of steps in the grid are NR-1,
          NT-1, NP-1. Similarly, the number of bodies that limit the grid
          along r, theta and phy are NR+1, NT+1 and NP+1

        The hive is delimited:
        - radially, by spheres;
        - on theta, by TRCs (i.e. identifying circles of latitude on the spherical shell);
        - on phi, by rotated YZPs (i.e. identifying meridians on the spherical shell);
        '''
        
        print("Preparing the hive for a spherical shell...")

        if (whichMaxLen is None):
            whichMaxLen="M"
        elif (not isinstance(whichMaxLen,str) or len(whichMaxLen.strip())==0):
            print("Please specify whichMaxLen as a non-empty string!")
            exit(1)
        elif (whichMaxLen.upper()[0] not in ["R","P","T","M"]):
            print("Please specify a suitable whichMaxLen: R(adius)/P(hi)/T(heta)/M(ax)!")
            exit(1)
        
        print("...generating the grid of cells...")
        cellGrid=grid.SphericalShell(Rmin,Rmax,NR,Tmin,Tmax,NT,Pmin,Pmax,NP,lDebug=lDebug)
        print("...defining hive boundaries...")
        myHive=grid.SphericalHive(Rmin,Rmax,NR,Tmin,Tmax,NT,Pmin,Pmax,NP,lDebug=lDebug)
        RRs,TTs,PPs=myHive.ret(what="all")

        print("...generating FLUKA geometry...")
        newGeom=Geometry()
        
        print("   ...bodies...")
        # - concentric spherical shells
        spheres=[]
        for ii,RR in enumerate(RRs,1):
            tmpBD=Body()
            tmpBD.rename("HVRAD%03i"%(ii),lNotify=False)
            tmpBD.bType="SPH"
            tmpBD.Rs[0]=RR
            tmpBD.comment="* Hive radial boundary at R[cm]=%g"%(RR)
            spheres.append(tmpBD)
        spheres[0].comment="* \n"+spheres[0].comment
        # - circles of latitude on the spherical shell
        thetas=[]
        for ii,TT in enumerate(TTs,1):
            tmpBD=Body()
            tmpBD.rename("HVTHT%03i"%(ii),lNotify=False)
            if (TT==0.0):
                tmpBD.V=np.array([0.0,1.0,0.0])
            else:
                tmpBD.bType="TRC"
                hh=RRs[-1]+10
                if ( myHive.SphericalHive_ThetaCoversPi() and ( ii==1 or ii==len(TTs) ) ):
                    # extremely small angle, almost 90degs,
                    #  almost negligible, but necessary for a more
                    #  robust geometry
                    tmpBD.Rs[0]=hh*1E-4
                else:
                    tmpBD.Rs[0]=hh*np.tan(np.radians(90-abs(TT)))
                if (TT>0):
                    hh=-hh # TT>0: angle towards y>0 --> TRC points downwards
                tmpBD.V=np.array([0.0, hh,0.0])
                tmpBD.P=np.array([0.0,-hh,0.0])
            tmpBD.comment="* Hive theta boundary at theta[deg]=%g"%(TT)
            thetas.append(tmpBD)
        thetas[0].comment="* \n"+thetas[0].comment
        # - meridians on the spherical shell
        phis=[]
        for ii,PP in enumerate(PPs,1):
            tmpBD=Body()
            tmpBD.rename("HVPHI%03i"%(ii),lNotify=False)
            tmpBD.V=np.array([1.0,0.0,0.0])
            tmpBD.rotate(myMat=None,myTheta=PP,myAxis=2,lDegs=True,lDebug=lDebug)
            tmpBD.comment="* Hive phi boundary at phi[deg]=%g"%(PP)
            phis.append(tmpBD)
        phis[0].comment="* \n"+phis[0].comment
        newGeom.bods=spheres+thetas+phis

        print("   ...regions...")
        # - outside hive
        tmpReg=Region()
        tmpReg.rename("HV_OUTER",lNotify=False)
        tmpReg.material=defMat
        tmpReg.addZone('-%-8s'%(spheres[-1].name))
        tmpReg.comment="* region outside hive"
        tmpReg.initCont(rCont=-1)
        newGeom.add(tmpReg,what="reg")
        # - inside hive
        tmpReg=Region()
        tmpReg.rename("HV_INNER",lNotify=False)
        tmpReg.material=defMat
        tmpReg.addZone('+%-8s'%(spheres[0].name))
        tmpReg.comment="* region inside hive"
        newGeom.add(tmpReg,what="reg")
        # - around hive
        tmpReg=Region()
        tmpReg.rename("HVAROUND",lNotify=False)
        tmpReg.material=defMat
        if (not cellGrid.HasPole("N")):
            tmpReg.addZone('+%-8s -%-8s +%-8s'%( \
                spheres[-1].echoName(),spheres[0].echoName(), thetas[-1].echoName() ))
        if (not cellGrid.HasPole("S")):
            tmpReg.addZone('+%-8s -%-8s +%-8s'%( \
                spheres[-1].echoName(),spheres[0].echoName(), thetas[ 0].echoName() ))
        if (not myHive.SphericalHive_PhiCovers2pi()):
            tmpReg.addZone('+%-8s -%-8s -%-8s -%-8s -%-8s +%-8s'%( \
                spheres[-1].echoName(),spheres[0].echoName(), thetas[-1].echoName(), thetas[ 0].echoName(), phis[-1].echoName(), phis[ 0].echoName() ))
        if (PPs[-1]-PPs[0]<180.0):
            tmpReg.addZone('+%-8s -%-8s -%-8s -%-8s -%-8s -%-8s'%( \
                spheres[-1].echoName(),spheres[0].echoName(), thetas[-1].echoName(), thetas[ 0].echoName(), phis[-1].echoName(), phis[ 0].echoName() ))
            tmpReg.addZone('+%-8s -%-8s -%-8s -%-8s +%-8s +%-8s'%( \
                spheres[-1].echoName(),spheres[0].echoName(), thetas[-1].echoName(), thetas[ 0].echoName(), phis[-1].echoName(), phis[ 0].echoName() ))
        if (tmpReg.isNonEmpty()):
            tmpReg.comment="* region around hive"
            newGeom.add(tmpReg,what="reg")
        # - actual hive
        iPs=[ iP for iP in range(1,len(phis)) ]
        if myHive.SphericalHive_PhiCovers2pi():
            # re-use first plane
            iPs=iPs+[0]
        iHive=0
        for iR in range(1,len(spheres)):
            if (cellGrid.HasPole("S")):
                tmpReg=Region()
                tmpReg.rename("HVCL%04i"%(iHive),lNotify=False)
                tmpReg.material=defMat
                tmpReg.addZone('+%-8s -%-8s +%-8s'%(spheres[iR].echoName(),spheres[iR-1].echoName(),thetas[0].echoName()))
                myCenter=cellGrid.ret(what="POINT",iEl=iHive)
                if (whichMaxLen.upper().startswith("R")):
                    rMaxLen=RRs[iR]-RRs[iR-1]
                elif (whichMaxLen.upper().startswith("P")):
                    rMaxLen=2*np.pi*RRs[iR]*np.sin(np.radians(TTs[0]-90))
                elif (whichMaxLen.upper().startswith("T")):
                    rMaxLen=RRs[iR]*2*np.absolute(np.radians(TTs[0]-90))
                else:
                    rMaxLen=max(RRs[iR]-RRs[iR-1],RRs[iR]*2*np.absolute(np.radians(TTs[0]-90)),2*np.pi*RRs[iR]*np.sin(np.radians(TTs[0]-90)))
                tmpReg.tailMe("* - hive region %4d: SOUTH POLE! R[cm]=[%g:%g], theta[deg]=[-90:%g]"%(
                    iHive,RRs[iR-1],RRs[iR],TTs[0]))
                tmpReg.tailMe("*   center=[%g,%g,%g];"%(myCenter[0],myCenter[1],myCenter[2]))
                tmpReg.initCont(rCont=1,rCent=myCenter,rMaxLen=rMaxLen)
                newGeom.add(tmpReg,what="reg")
                iHive=iHive+1
            for iT in range(1,len(thetas)):
                for iP in iPs:
                    tmpReg=Region()
                    tmpReg.rename("HVCL%04i"%(iHive),lNotify=False)
                    tmpReg.material=defMat
                    rDef='+%-8s -%-8s'%(spheres[iR].echoName(),spheres[iR-1].echoName())
                    if (TTs[iT]<=0.0):
                        tDef='+%-8s -%-8s'%(thetas [iT].echoName(),thetas [iT-1].echoName())
                    elif (TTs[iT-1]==0.0 or (TTs[iT]>0.0 and TTs[iT-1]<0.0)):
                        tDef='-%-8s -%-8s'%(thetas [iT].echoName(),thetas [iT-1].echoName())
                    elif (TTs[iT-1]>0.0):
                        tDef='-%-8s +%-8s'%(thetas [iT].echoName(),thetas [iT-1].echoName())
                    pDef='+%-8s -%-8s'%(phis[iP].echoName(),phis[iP-1].echoName())
                    tmpReg.addZone('%s %s %s'%(rDef,tDef,pDef))
                    myCenter=cellGrid.ret(what="POINT",iEl=iHive)
                    if (whichMaxLen.upper().startswith("R")):
                        rMaxLen=RRs[iR]-RRs[iR-1]
                    elif (whichMaxLen.upper().startswith("P")):
                        rMaxLen=RRs[iR]*np.radians(PPs[iT]-PPs[iT-1])
                    elif (whichMaxLen.upper().startswith("T")):
                        rMaxLen=RRs[iR]*np.radians(TTs[iT]-TTs[iT-1])
                    else:
                        rMaxLen=max(RRs[iR]-RRs[iR-1],RRs[iR]*np.radians(TTs[iT]-TTs[iT-1]),RRs[iR]*np.radians(PPs[iT]-PPs[iT-1]))
                    tmpReg.tailMe("* - hive region %4d: R[cm]=[%g:%g], theta[deg]=[%g:%g], phi[deg]=[%g:%g]"%(
                        iHive,RRs[iR-1],RRs[iR],TTs[iT-1],TTs[iT],PPs[iP-1],PPs[iP]))
                    tmpReg.tailMe("*   center=[%g,%g,%g];"%(myCenter[0],myCenter[1],myCenter[2]))
                    tmpReg.initCont(rCont=1,rCent=myCenter,rMaxLen=rMaxLen)
                    newGeom.add(tmpReg,what="reg")
                    iHive=iHive+1
            if (cellGrid.HasPole("N")):
                tmpReg=Region()
                tmpReg.rename("HVCL%04i"%(iHive),lNotify=False)
                tmpReg.material=defMat
                tmpReg.addZone('+%-8s -%-8s +%-8s'%(spheres[iR].echoName(),spheres[iR-1].echoName(),thetas[-1].echoName()))
                myCenter=cellGrid.ret(what="POINT",iEl=iHive)
                if (whichMaxLen.upper().startswith("R")):
                    rMaxLen=RRs[iR]-RRs[iR-1]
                elif (whichMaxLen.upper().startswith("P")):
                    rMaxLen=2*np.pi*RRs[iR]*np.sin(np.radians(90-TTs[-1]))
                elif (whichMaxLen.upper().startswith("T")):
                    rMaxLen=RRs[iR]*2*np.absolute(np.radians(90-TTs[-1]))
                else:
                    rMaxLen=max(RRs[iR]-RRs[iR-1],RRs[iR]*2*np.absolute(np.radians(90-TTs[-1])),2*np.pi*RRs[iR]*np.sin(np.radians(90-TTs[-1])))
                tmpReg.tailMe("* - hive region %4d: NORTH POLE! R[cm]=[%g:%g], theta[deg]=[%g:90]"%(
                    iHive,RRs[iR-1],RRs[iR],TTs[-1]))
                tmpReg.tailMe("*   center=[%g,%g,%g];"%(myCenter[0],myCenter[1],myCenter[2]))
                tmpReg.initCont(rCont=1,rCent=myCenter,rMaxLen=rMaxLen)
                newGeom.add(tmpReg,what="reg")
                iHive=iHive+1

        newGeom.headMe(tmpTitle)
        newGeom.setTitle(tmpTitle=tmpTitle)

        if (lWrapBHaround):
            newGeom=Geometry.WrapBH_Sphere(newGeom,2*max(RRs),3*max(RRs))
        return newGeom

    @staticmethod
    def BuildGriddedGeo(myGrid,myProtoList,myProtoGeos,osRegNames=[],lLattice=False,lTrigScoring=None,lGeoDirs=False,lDebug=True):
        '''
        This method defines a list of FLUKA geometry representing a grid of objects.

        input parameters:
        - grid: an instance of a Grid() class, i.e. a list of locations;
        - myProtoList: this list states which prototype should be used at each
                       location. NB: len(myProtoList)=len(myGrid);
        - myProtoGeos: dictionary of actual prototype geometries. The unique
                       entries of myProtoList are the full set or a subset of
                       the keys of this dictionary;
        - osRegNames:  list of regions of the prototypes expressing the outermost
                       part of the prototypes, to be 'subtracted' from the region
                       definition of the hive cells, that should be sized by the
                       regions of the hive cell;
        - lTrigScoring: this list states if the gridded geometries should have
                        a copy of the scoring cards declared with the prototype;
        '''
        print("building gridded geometry...")
        if (lTrigScoring is None): lTrigScoring=True
        if (not isinstance(lTrigScoring,list)): lTrigScoring=[ lTrigScoring for ii in range(myGrid) ]
        myGeos=[]
        if (lLattice): protoSeen={ key: -1 for key in list(myProtoGeos) }
        # loop over locations, to clone prototypes
        for iLoc,myLoc in enumerate(myGrid):
            if (lDebug): print("...grid cell %3d/%3d..."%(iLoc+1,len(myGrid)))
            if (myProtoList[iLoc] not in myProtoGeos):
                print("Geometry.BuildGriddedGeo(): unknown prototype %s!"%(\
                        myProtoList[iLoc]))
                exit(1)
            # - clone prototype
            if ( not lLattice or protoSeen[myProtoList[iLoc]]==-1 ):
                if (lDebug): print("...real geometry...")
                myGeo=Geometry.ActualCopy(myProtoGeos[myProtoList[iLoc]],lTrigScoring=lTrigScoring[iLoc])
                if (lLattice): protoSeen[myProtoList[iLoc]]=iLoc
            else:
                if (lDebug): print("...LATTICE cell...")
                myGeo=Geometry.LatticeCopy(myProtoGeos[myProtoList[iLoc]],lTrigScoring=lTrigScoring[iLoc])
            # - move clone to requested location/orientation
            #   NB: give priority to angles/axis wrt matrices, for higher
            #       numerical accuracy in final .inp file
            if (len(myLoc.ret("ANGLE"))>0):
                # angle/axis pair
                if (lLattice and iLoc!=protoSeen[myProtoList[iLoc]]):
                    protoLoc=myGrid.ret(what="LOC",iEl=protoSeen[myProtoList[iLoc]])
                    dd=-protoLoc.ret("POINT")
                    myGeo.solidTrasform(dd=dd,lGeoDirs=lGeoDirs,lOnlyGeo=True,lDebug=lDebug)
                    myTheta=[ -angle for angle in reversed(protoLoc.ret("ANGLE")) ]
                    myAxis=[ axis for axis in reversed(protoLoc.ret("AXIS")) ]
                    myGeo.solidTrasform(myTheta=myTheta,myAxis=myAxis,lGeoDirs=lGeoDirs,lOnlyGeo=True,lDebug=lDebug)
                dd=myLoc.ret("POINT")
                myTheta=myLoc.ret("ANGLE")
                myAxis=myLoc.ret("AXIS")
                myGeo.solidTrasform(dd=dd,myTheta=myTheta,myAxis=myAxis,lGeoDirs=lGeoDirs,lDebug=lDebug)
            else:
                # matrix
                if (lLattice and iLoc!=protoSeen[myProtoList[iLoc]]):
                    protoLoc=myGrid.ret(what="LOC",iEl=iLoc)
                    dd=-protoLoc.ret("POINT")
                    myGeo.solidTrasform(dd=dd,lGeoDirs=lGeoDirs,lDebug=lDebug)
                    myMat=protoLoc.ret("MATRIX").inv()
                    myGeo.solidTrasform(myMat=myMat,lGeoDirs=lGeoDirs,lOnlyGeo=True,lDebug=lDebug)
                dd=myLoc.ret("POINT")
                myMat=myLoc.ret("MATRIX")
                myGeo.solidTrasform(dd=dd,myMat=myMat,lGeoDirs=lGeoDirs,lDebug=lDebug)
            # - flag the region(s) outside the prototypes or that should be sized
            #   by the hive cells
            if (not lLattice or iLoc==protoSeen[myProtoList[iLoc]]):
                myGeo.flagRegs(osRegNames,-1,myLoc.ret("POINT"))
            else:
                myGeo.flagRegs(["LATREG"],-1,myLoc.ret("POINT"))
            # - rename the clone
            baseName="GR%03d"%(iLoc)
            myGeo.rename(baseName)
            # - notify the user about original prototype and location
            myGeo.headMe("GRID cell # %3d - family name: %s - prototype: %s\n"%(\
                            iLoc,baseName,myProtoList[iLoc])+ \
                         "* "+myLoc.echo(myFmt="% 13.6E",mySep="\n* ") )
            # - append clone to list of geometries
            myGeos.append(myGeo)
        # return merged geometry
        print("...built %d grid elements!"%(len(myGeos)))
        return myGeos

    @staticmethod
    def MergeGeos(hiveGeo,gridGeo,mapping,mapType,lDebug=True,myTitle=None):
        '''
        This method merges one FLUKA geometry onto another one.

        input parameters:
        - hiveGeo: Geometry instance of the hive;
        - gridGeo: Geometry instance of the grid of objects;
        - mapping: dictionary:
          . mapping["iRhg"][ii]: ii-th hive region;
          . mapping["jRhg"][ii]: ii-th element in list of hive geometries;
          . mapping["iRgg"][ii]: ii-th grid region;
          . mapping["jRgg"][ii]: ii-th element in list of grid geometries;
        - mapType:
          . "oneHive": one hive region contains one or more grid regions;
          . "oneGrid": one grid region is contained in one or more hive regions;

        The two geometries must not have common names - no check is performed
          for the time being.
        '''
        print("merging geometries...")
        if (lDebug): print("...using %s map type;"%(mapType))
        removeRegs=[]; jRemoveRegs=[]
        if (mapType=="oneHive"):
            # for each location, only one hive region is concerned:
            #   merge each containing hive region into the concerned
            #   grid regions, and then remove the hive region
            # - merge defs
            lFirst=True
            for iRhg,jRhg,iRgg,jRgg in zip(mapping["iRhg"],mapping["jRhg"],mapping["iRgg"],mapping["jRgg"]):
                # copy comment of hive region only in the first instance of the grid
                gridGeo[jRgg].regs[iRgg].merge(hiveGeo[jRhg].regs[iRhg],lCopyComment=lFirst)
                if (hiveGeo[jRhg].regs[iRhg].echoName() not in removeRegs):
                    removeRegs.append(hiveGeo[jRhg].regs[iRhg].echoName())
                    jRemoveRegs.append(jRhg)
                if (lFirst): lFirst=False
            # - remove merged regs
            for removeReg,jRemoveReg in zip(removeRegs,jRemoveRegs):
                myReg,iReg=hiveGeo[jRemoveReg].ret("REG",removeReg)
                hiveGeo[jRemoveReg].regs.pop(iReg)
        elif(mapType=="oneGrid"):
            # for each location, only one grid region is concerned:
            #   merge each contained grid region into the concerned
            #   hive regions, and then remove the grid region
            # - merge defs
            for iRhg,jRhg,iRgg,jRgg in zip(mapping["iRhg"],mapping["jRhg"],mapping["iRgg"],mapping["jRgg"]):
                hiveGeo[jRhg].regs[iRhg].merge(gridGeo[jRgg].regs[iRgg])
                if (gridGeo[jRgg].regs[iRgg].echoName() not in removeRegs):
                    removeRegs.append(gridGeo[jRgg].regs[iRgg].echoName())
                    jRemoveRegs.append(jRgg)
            # - remove merged regs
            for removeReg,jRemoveReg in zip(removeRegs,jRemoveRegs):
                myReg,iReg=gridGeo[jRemoveReg].ret("REG",removeReg)
                gridGeo[jRemoveReg].regs.pop(iReg)
        else:
            print("...wrong specification of mapping: %s!"%(mapType))
            exit(1)
        return Geometry.appendGeometries(hiveGeo+gridGeo,myTitle=myTitle)

    @staticmethod
    def WrapBH_Sphere(myGeo,Rmin,Rmax,defMat="VACUUM",lDebug=True):
        '''
        Method for wrapping a spherical layer of blackhole around a given geometry
        '''
        print('wrapping a spherical layer of blackhole around geometry: Rmin=%g; Rmax=%g'%(Rmin,Rmax))
        newGeom=Geometry()

        print("...bodies...")
        bodies=[]
        for RR,tagName in zip([Rmin,Rmax],["inner","outer"]):
            tmpBD=Body()
            tmpBD.rename("BLK%s"%(tagName.upper()),lNotify=False)
            tmpBD.bType="SPH"
            tmpBD.Rs[0]=RR
            tmpBD.comment="* blackhole: %s radial boundary at R[cm]=%g"%(tagName,RR)
            bodies.append(tmpBD)
            
        print("...regions...")
        regions=[]
        # - regions outside / inside layer
        for iBod, (tagName,mySig,myPos) in enumerate(zip(["inner","outer"],["+","-"],["inside","outside"])):
            tmpReg=Region()
            tmpReg.rename("BLK%s"%(tagName.upper()),lNotify=False)
            tmpReg.material=defMat
            tmpReg.definition='''%s%-8s'''%(mySig,bodies[iBod].name)
            tmpReg.comment="* region %s blakchole layer"%(myPos)
            if (iBod==0):
                tmpReg.initCont(rCont=1)
            regions.append(tmpReg)
        # - actual layer
        tmpReg=Region()
        tmpReg.rename("BLKLAYER",lNotify=False)
        tmpReg.material="BLCKHOLE"
        tmpReg.definition='''+%-8s -%-8s'''%(bodies[-1].echoName(),bodies[0].echoName())
        tmpReg.comment="* blackhole layer"
        regions.append(tmpReg)

        newGeom.bods=bodies
        newGeom.regs=regions

        newGeom,myGeo,mapping,mapType=MapGridLocsOntoHiveLocs(newGeom,myGeo,lDebug=lDebug)
        mergedGeo=Geometry.MergeGeos(newGeom,myGeo,mapping,mapType,lDebug=lDebug,myTitle=myGeo.title)
        print('...done.')
        return mergedGeo

    @staticmethod
    def CreateSlicingGeo(zLocs,P0=np.zeros(3),VV=np.array([0.0,0.0,1.0]),defMat="VACUUM",tmpTitle="Slicing Planes"):
        '''
        Method for generating a geometry made of a series of planes slicing something
        '''
        print('generating a slicing geometry...')
        aP0=np.array(P0)
        aVV=VV/np.linalg.norm(VV)
        
        newGeom=Geometry()
        for ii,zLoc in enumerate(zLocs):
            # body
            tmpBD=Body(myName="BOUND%03i"%(ii+1),myComment="* boundary at z=%g"%(zLoc))
            tmpBD.P=aP0+zLoc*aVV
            tmpBD.V=aVV
            # region
            tmpReg=Region(myName="SLICE%03i"%(ii+1))
            if (ii==0):
                tmpReg.comment="* first slice"
                tmpReg.addZone("+%-8s"%(tmpBD.name))
            else:
                tmpReg.comment="* range of slice: [%g:%g]"%(zLoc,zLocs[ii-1])
                tmpReg.addZone("+%-8s -%-8s"%(tmpBD.name,newGeom.bods[-1].name))
            tmpReg.material=defMat
            # adding
            newGeom.add(tmpBD,what="bod")
            newGeom.add(tmpReg,what="reg")
        # last slice
        tmpReg=Region(myName="SLICE%03i"%(ii+2))
        tmpReg.comment="* last slice"
        tmpReg.addZone("-%-8s"%(newGeom.bods[-1].name))
        tmpReg.material=defMat
        newGeom.add(tmpReg,what="reg")
        
        newGeom.headMe(tmpTitle)
        newGeom.setTitle(tmpTitle=tmpTitle)

        print('...generated %d bodies and %d regions;'%(len(newGeom.bods),len(newGeom.regs)))
        return newGeom

    def SliceGeo(self,regName,zLocs,bodName=None,P0=None,VV=None,matName=None,RegBasedScorNames=[],lDebug=True):
        '''
        Method for slicing an existing geometry:
        - regName: name of region to be sliced;
        - zLocs: longitudinal positions [cm] at which the region should be sliced;
        - bodName: name of body from which starting point and direction of
                   slicing should be taken;
        - RegBasedScorNames: names of region-based scorings that should be replicated
                    following slicing;
        - P0,VV: starting point and orientation array for slicing;

        NB: the method applies to any region which is encapsulated in an RPP or an RCC
        '''
        print("slicing region %s into %d sections..."%(regName,len(zLocs)+1))
        # - checks
        reg2Bsliced,iReg=self.ret("reg",regName)
        if (reg2Bsliced is None):
            print("   ...region %s NOT found!"%(regName))
            exit(1)
        if (matName is None): matName=reg2Bsliced.material
        if (P0 is None and VV is None):
            if (bodName is None): bodName=regName # default
            print("...starting position and orientation as from body %s..."%(bodName))
            orientingBody,iBod=self.ret("bod",bodName)
            if (orientingBody is None):
                print("   ...body %s NOT found!"%(bodName))
                exit(1)
            # - get infos
            P0=orientingBody.retCenter(myType=-1)
            VV=orientingBody.retOrient()
        elif (P0 is not None and VV is     None):
            print("Geometry.SliceGeo(): incomplete input, VV is None!")
            exit(1)
        elif (P0 is     None and VV is not None):
            print("Geometry.SliceGeo(): incomplete input, P0 is None!")
            exit(1)
        if (len(P0)!=3):
            print("Geometry.SliceGeo(): len(P0)!=3!")
            exit(1)
        if (len(VV)!=3):
            print("Geometry.SliceGeo(): len(VV)!=3!")
            exit(1)
        if (lDebug):
            print("...starting position: [%g,%g,%g];"%(P0[0],P0[1],P0[2]))
            print("...orientation:       [%g,%g,%g];"%(VV[0],VV[1],VV[2]))
        # - build slicing geo and flag it for merging
        slicingGeo=Geometry.CreateSlicingGeo(zLocs,P0=P0,VV=VV,defMat=matName)
        # - take care of reg-based scorings
        origScos=[]
        if (isinstance(RegBasedScorNames,str)):
            if (RegBasedScorNames.upper()=="ALL"):
                origScos=deepcopy(self.scos)
                self.scos=[]
            else:
                sco2duplicate,iSco=self.ret("sco",RegBasedScorNames)
                if (sco2duplicate is None):
                    print("   ...reg-based scoring %s NOT found!"%(regBasedScorNames))
                    exit(1)
                origScos.append(self.scos.pop(iSco))
        else:
            for regBasedScorName in RegBasedScorNames:
                sco2duplicate,iSco=self.ret("sco",regBasedScorName)
                if (sco2duplicate is None):
                    print("   ...reg-based scorings %s NOT found!"%(regBasedScorName))
                    exit(1)
                origScos.append(self.scos.pop(iSco))
        if (len(origScos)>0):
            print("duplicating scorings")
            allRegNames,iRegs=slicingGeo.ret("REG","ALL")
            allBodNames,iBods=slicingGeo.ret("BOD","ALL")
            # 2-reg based scoring cards:
            for reg1name,reg2name,myBodName in zip(allRegNames[0:-1],allRegNames[1:],allBodNames):
                myBod,iBod=slicingGeo.ret("BOD",myBodName)
                lFirst=True
                for origSco in origScos:
                    if (isinstance(origSco,Usryield) or isinstance(origSco,Usrbdx)):
                        newSco=deepcopy(origSco)
                        newSco.setRegName(1,reg1name)
                        newSco.setRegName(2,reg2name)
                        if (lFirst):
                            newSco.tailMe(myBod.echoComm().strip())
                            lFirst=False
                        slicingGeo.add(newSco,"SCO")
            # 1-reg based scoring cards:
            for tRegName in allRegNames:
                myReg,iReg=slicingGeo.ret("Reg",tRegName)
                lFirst=True
                for origSco in origScos:
                    if (isinstance(origSco,Usrcoll) or isinstance(origSco,Usrtrack)):
                        newSco=deepcopy(origSco)
                        newSco.setRegName(tRegName)
                        if (lFirst):
                            newSco.tailMe(myReg.echoComm().strip())
                            lFirst=False
                        slicingGeo.add(newSco,"SCO")
        # - rename geometry entities
        slicingGeo.rename(regName)
        # - flag regions for merging and create mapping
        slicingGeo.flagRegs("all",rCont=-1)
        reg2Bsliced.initCont(rCont=1)
        HiveGeo,GridGeo,mapping,mapType=MapContRegs(self,slicingGeo,lDebug=lDebug)
        # - return merged geo
        return Geometry.MergeGeos(HiveGeo,GridGeo,mapping,mapType)

    def insertGeoInGeo(self,geoToInsert,extName,regName,lDebug=True):
        if (lDebug): print("inserting geometry...")
        # - outer region of geometry to insert
        if (isinstance(extName,list)):
            extNames=extName
        elif (isinstance(extName,str)):
            extNames=[extName]
        for myName in extNames:
            myReg,iReg=geoToInsert.ret("Reg",myName)
            if (myReg is None):
                print("...region %s NOT found in geometry to insert!"%(myName))
                exit(1)
            else:
                myReg.initCont(rCont=-1)
        # - region of outer geometry where to insert geometry
        if (isinstance(regName,list)):
            regNames=regName
        elif (isinstance(regName,str)):
            regNames=[regName]
        for myName in regNames:
            myReg,iReg=self.ret("Reg",myName)
            if (myReg is None):
                print("...region %s NOT found in hosting geometry!"%(myName))
                exit(1)
            else:
                myReg.initCont(rCont=1)
        # - merge
        HiveGeo,GridGeo,mapping,mapType=MapContRegs(self,geoToInsert,lDebug=lDebug)
        return Geometry.MergeGeos(HiveGeo,GridGeo,mapping,mapType)

def acquireGeometries(fileNames,geoNames=None,lMakeRotatable=False):
    '''
    A simple function to parse a series of geometry files and
      store them in a dictionary of geometries.
    This function can be used to parse the database of prototype geometries.
    '''
    import os.path
    # check user input
    if (geoNames is None):
        geoNames=fileNames
    elif (len(fileNames)!=len(geoNames)):
        print("Number of items (%d) and names (%d) of geometries to acquire do not coincide!"%\
              (len(fileNames),len(geoNames)))
        exit(1)
        
    # acquire geometries:
    print("acquiring geometries...")
    myGeos={}
    for ii in range(len(fileNames)):
        if (not os.path.isfile(fileNames[ii]) or not os.path.exists(fileNames[ii])):
            print("something wrong with file %s! please check path, existence, access rights!"%(fileNames[ii]))
            exit(1)
        myGeos[geoNames[ii]]=Geometry.fromInp(fileNames[ii])
        if (geoNames[ii]!=fileNames[ii]):
            print("--> geometry saved in DB as %s;"%(geoNames[ii]))
    print("...acquired %d/%d geometries;"%(len(myGeos),len(fileNames)))

    # make geometries rotatable
    if (lMakeRotatable):
        print("making acquired geometries rotatable...")
        for myProtoName,myProtoGeo in myGeos.items():
            myProtoGeo.makeBodiesRotatable()
        print("...done;")
        
    return myGeos

def MapGridLocsOntoHiveLocs(hiveGeo,gridGeo,lDebug=True,prec=0.001):
    '''
    This method maps a grid of FLUKA geometries onto the hive based
      on the center coordinates of containing and contained regions.

    input parameters:
    - hiveGeo: list of Geometry instance(s) of the hive;
    - gridGeo: list of Geometry instance(s) of the grid;
    - prec: precision of identification of points proximity [cm];

    output parameters:
    - mapping: dictionary:
      . mapping["iRhg"][ii]: ii-th hive region;
      . mapping["jRhg"][ii]: ii-th element in list of hive geometries;
      . mapping["iRgg"][ii]: ii-th grid region;
      . mapping["jRgg"][ii]: ii-th element in list of grid geometries;
    - mapType:
      . "oneHive": one hive region contains one or more grid regions;
      . "oneGrid": one grid region is contained in one or more hive regions;

    All the regions of gridGeo with rCont==-1 will be matched with regions
      of hiveGeo with rCont==1 if they have the same center coordinates via
      a one-to-one mapping established based on the rCent arrays.
    '''
    print("mapping grid and hive geometries based on region flagging and center coordinates...")
    if (isinstance(hiveGeo,Geometry)): hiveGeo=[hiveGeo]
    if (isinstance(gridGeo,Geometry)): gridGeo=[gridGeo]
    # hiveGeo
    iRhgs=[]; jRhgs=[]; cRhgs=[];
    for jj,myGeo in enumerate(hiveGeo):
        iRhgs=iRhgs+[ ii for ii,mReg in enumerate(myGeo.regs) if mReg.rCont==1 ]
        jRhgs=jRhgs+[ jj for mReg in myGeo.regs if mReg.rCont==1 ]
        cRhgs=cRhgs+[ mReg.rCent for mReg in myGeo.regs if mReg.rCont==1 ]
    cRhgs=np.array(cRhgs)
    ucRhgs=np.unique(cRhgs,axis=0)
    # gridGeo
    iRggs=[]; jRggs=[]; cRggs=[];
    for jj,myGeo in enumerate(gridGeo):
        iRggs=iRggs+[ ii for ii,mReg in enumerate(myGeo.regs) if mReg.rCont==-1 ]
        jRggs=jRggs+[ jj for mReg in myGeo.regs if mReg.rCont==-1 ]
        cRggs=cRggs+[ mReg.rCent for mReg in myGeo.regs if mReg.rCont==-1 ]
    cRggs=np.array(cRggs)
    ucRggs=np.unique(cRggs,axis=0)
    # output
    mapping={"iRhg":[],"jRhg":[],"iRgg":[],"jRgg":[]}
    if (lDebug):
        print("...found %d containing regions in hive:"%(len(iRhgs)))
        print("   ...with %d unique centers!"%(len(ucRhgs)))
        print(iRhgs)
        print(jRhgs)
        print(cRhgs)
        print(ucRhgs)
        print("...found %d contained/sized regions in grid:"%(len(iRggs)))
        print("   ...with %d unique centers!"%(len(ucRggs)))
        print(iRggs)
        print(jRggs)
        print(cRggs)
        print(ucRggs)
    if (len(iRhgs)==len(ucRhgs)):
        # for each location, only one hive region is concerned:
        #   merge each containing hive region into the concerned
        #   grid region(s), and then remove the hive region
        mapType="oneHive"
        for iRhg,jRhg in zip(iRhgs,jRhgs):
            for iRgg,jRgg in zip(iRggs,jRggs):
                if (np.linalg.norm(gridGeo[jRgg].regs[iRgg].rCent-hiveGeo[jRhg].regs[iRhg].rCent)<prec):
                    mapping["iRhg"].append(iRhg)
                    mapping["jRhg"].append(jRhg)
                    mapping["iRgg"].append(iRgg)
                    mapping["jRgg"].append(jRgg)
    elif(len(iRggs)==len(ucRggs)):
        # for each location, only one grid region is concerned:
        #   merge each contained grid region into the concerned
        #   hive region(s), and then remove the grid region
        mapType="oneGrid"
        for iRgg,jRgg in zip(iRggs,jRggs):
            for iRhg,jRhg in zip(iRhgs,jRhgs):
                if (np.linalg.norm(gridGeo[jRgg].regs[iRgg].rCent-hiveGeo[jRhg].regs[iRhg].rCent)<prec):
                    mapping["iRhg"].append(iRhg)
                    mapping["jRhg"].append(jRhg)
                    mapping["iRgg"].append(iRgg)
                    mapping["jRgg"].append(jRgg)
    else:
        print("...cannot map more than a region of the hive and more than a region of the grid for a single location!")
        exit(1)
        
    return hiveGeo, gridGeo, mapping, mapType

def MapContRegs(CtainGeo,CinedGeo,lDebug=True):
    '''
    This method maps the region(s) of a FLUKA geometry containing
      the region(s) of another FLUKA geometry. Supported cases:
    - a single container region and multiple contained regions;
    - multiple container regions and a single contained region;
    For multi-regions containing multi-regions, please use the
      mapping function based on region centres.

    input parameters:
    - CtainGeo: Geometry instance with the container region(s);
    - CinedGeo: Geometry instance with the contained region(s).

    output parameters:
    - mapping: dictionary:
      . mapping["iRhg"][ii]: ii-th containing region(s);
      . mapping["jRhg"][ii]: ii-th element in list of geometries with continaing regions;
      . mapping["iRgg"][ii]: ii-th contained region(s);
      . mapping["jRgg"][ii]: ii-th element in list of geometries with contained regions;
    - mapType:
      . "oneHive": one hive region contains one or more grid regions;
      . "oneGrid": one grid region is contained in one or more hive regions;

    All the regions of CinedGeo with rCont==-1 will be matched with regions
      of CtainGeo with rCont==1.
    '''
    # output
    print("mapping grid and hive geometries based on region flagging only...")
    mapping={"iRhg":[],"iRgg":[]}
    iRhgs=[ ii for ii,mReg in enumerate(CtainGeo.regs) if mReg.rCont==1 ]
    iRggs=[ ii for ii,mReg in enumerate(CinedGeo.regs) if mReg.rCont==-1 ]
    if (lDebug):
        print("...found %d containing regions:"%(len(iRhgs)))
        print(iRhgs)
        print("...found %d contained regions:"%(len(iRggs)))
        print(iRggs)
    if (len(iRhgs)>1 and len(iRggs)>1):
        print("Cannot merge many contained regions into many containing regions!")
        exit(1)
    elif (len(iRhgs)>=1 and len(iRggs)==1):
        # multiple containing regions for a single contained region
        mapType="oneGrid"
        if (lDebug): print("...one contained region and %d containing regions;"%(len(iRhgs)))
        #   merge each contained grid region into the concerned
        #   hive region(s), and then remove the grid region
        mapping["iRhg"]=iRhgs
        mapping["iRgg"]=[ iRggs[0] for iRhg in iRhgs ]
    else:
        # a single containing regions for multiple contained regions
        mapType="oneHive"
        if (lDebug): print("...one containing region and %d contained regions;"%(len(iRggs)))
        #   merge each containing region into the concerned
        #   contained region(s), and then remove the container region
        mapping["iRhg"]=[ iRhgs[0] for iRgg in iRggs ]
        mapping["iRgg"]=iRggs
    # keep compatibility with MergeGeos
    if (isinstance(CtainGeo,Geometry)): CtainGeo=[CtainGeo]
    if (isinstance(CinedGeo,Geometry)): CinedGeo=[CinedGeo]
    mapping["jRhg"]=[ 0 for iRhg in mapping["iRhg"] ]
    mapping["jRgg"]=[ 0 for iRgg in mapping["iRgg"] ]
    if (lDebug): print(mapping)
    return CtainGeo, CinedGeo, mapping, mapType

def ResizeBodies(hiveGeo,gridGeo,mapping,lDebug=True,enlargeFact=1.1):
    if (enlargeFact is not None):
        print("resizing grid bodies...")
        for iRhg,jRhg,iRgg,jRgg in zip(mapping["iRhg"],mapping["jRhg"],mapping["iRgg"],mapping["jRgg"]):
            newL=enlargeFact*hiveGeo[jRhg].regs[iRhg].rMaxLen
            gridGeo[jRgg].resizeBodies(newL,lDebug=lDebug)
        print("...done;")
    return gridGeo

def ResizeUSRBINs(hiveGeo,gridGeo,mapping,lDebug=True,enlargeFact=1.1,resBins="ALL"):
    if (enlargeFact is not None and resBins is not None):
        print("resizing USRBINs...")
        for iRhg,jRhg,iRgg,jRgg in zip(mapping["iRhg"],mapping["jRhg"],mapping["iRgg"],mapping["jRgg"]):
            newL=enlargeFact*hiveGeo[jRhg].regs[iRhg].rMaxLen
            gridGeo[jRgg].resizeUsrbins(newL,whichUnits=resBins,lDebug=lDebug)
        print("...done;")
    return gridGeo

if (__name__=="__main__"):
    lDebug=False
    lGeoDirs=False
    lLattice=True
    echoHiveInp="hive.inp"
    echoGridInp="grid.inp"
    osRegNames=["OUTER"]
    # # - manipulate a geometry
    # caloCrysGeo=Geometry.fromInp("caloCrys.inp")
    # myMat=RotMat(myAng=60,myAxis=3,lDegs=True,lDebug=lDebug)
    # caloCrysGeo.solidTrasform(dd=[0,10,-20],myMat=myMat)
    # caloCrysGeo.echo("pippo.inp")
    
    # - test generation of geometry
    R=75
    dR=50
    Rmin=R
    Rmax=R+dR
    NR=2
    Tmin=-20.0 # theta [degs] --> range: -Tmax:Tmax
    Tmax=20.0  # theta [degs] --> range: -Tmax:Tmax
    NT=4       # number of steps (i.e. grid cells)
    Pmin=-7.5
    Pmax=7.5   # phi [degs] --> range: -Pmax:Pmax
    NP=5       # number of steps (i.e. grid cells)
    
    # - hive geometry
    HiveGeo=Geometry.DefineHive_SphericalShell(Rmin,Rmax,NR,Tmin,Tmax,NT,Pmin,Pmax,NP,whichMaxLen=None,lDebug=lDebug)
    if (echoHiveInp is not None): HiveGeo.echo(echoHiveInp)
    
    # - gridded geometry
    #   acquire prototype geometries
    fileNames=[ "caloCrys_02.inp" ] ; geoNames=fileNames
    myProtoGeos=acquireGeometries(fileNames,geoNames=geoNames,lMakeRotatable=not lGeoDirs);
    #   generate gridded geometry:
    #   . generate grid
    cellGrid=grid.SphericalShell(R,R+dR,NR,-Tmax,Tmax,NT,Pmin,Pmax,NP,lDebug=lDebug)
    #   . associate a prototype to each cell
    myProtoList=[ "caloCrys_02.inp" for ii in range(len(cellGrid)) ]
    lTrigScoring=[ (0<=ii and ii<=2) for ii in range(len(cellGrid)) ]
    #   . generate geometry
    GridGeo=Geometry.BuildGriddedGeo(cellGrid,myProtoList,myProtoGeos,osRegNames=osRegNames,lLattice=lLattice,lTrigScoring=lTrigScoring,lGeoDirs=lGeoDirs,lDebug=lDebug)
    if (echoGridInp is not None): (Geometry.appendGeometries(GridGeo)).echo(echoGridInp)
    
    # - merge geometries
    #   get mapping (HiveGeo and GridGeo become lists, in case they are simple instances of Geoemtry)
    HiveGeo,GridGeo,mapping,mapType=MapGridLocsOntoHiveLocs(HiveGeo,GridGeo,lDebug=lDebug)
    GridGeo=ResizeBodies(HiveGeo,GridGeo,mapping,lDebug=lDebug)
    GridGeo=ResizeUSRBINs(HiveGeo,GridGeo,mapping,lDebug=lDebug,resBins=25)
    mergedGeo=Geometry.MergeGeos(HiveGeo,GridGeo,mapping,mapType,lDebug=lDebug)
    mergedGeo.reAssiginUSRBINunits(nMaxBins=35*35*5000,usedUnits=26)
    mergedGeo.echo("merged.inp")
