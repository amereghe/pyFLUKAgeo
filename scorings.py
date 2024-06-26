# classes for managing FLUKA scoring cards and detectors
# A. Mereghetti, 2024/04/16
# python version: >= 3.8.10

from FLUKA import GeoObject, echoFloats

class Usrbin(GeoObject):
    '''
    A very basic class for handling USRBIN cards.
    For the time being, there is support only for:
    - the scoring is not really interpreted: the FLUKA definition is kept in
      memory, and manipulations are performed on-the-fly;
    - parsing/echoing, ALWAYS in FIXED format;
    - always 2 cards to fully define scoring;
    - a single ROTPRBIN card per transformation (1:1 mapping between ROTPRBIN and
      USRBIN cards); the mapping to the transformation is ALWAYS name-based;
      the ROTPRBIN card always PRECEEDs the respective USRBIN card;
    - NO comments between USRBIN cards defining the same scoring detector;
    - manipulation of unit, extremes and numbers of bins; nevertheless,
      NO check is performed between the requested axis for manipulation and
      the type of mesh;
    '''
    def __init__(self,myName="",myComment=""):
        GeoObject.__init__(self,myName=myName,myComment=myComment)
        self.definition=[] # array of strings storing the lines defining the
                           #   USRBIN. NB: USRBIN tags, & char and bin name
                           #   are NOT stored.
        self.TransfName=""

    def echo(self):
        '''take into account comment'''
        tmpBuf=GeoObject.echoComm(self)
        if (len(self.TransfName)>0):
            tmpBuf=tmpBuf+"%-10s%10s%10s%10s%10s\n"\
                %("ROTPRBIN","",self.TransfName,"",self.echoName())
        for myDef,mySdum,myEoL in zip(self.definition,[self.echoName(),"&"],["\n",""]):
            tmpBuf=tmpBuf+"%-10s%60s%-10s%-s"%("USRBIN",myDef,mySdum,myEoL)
        return tmpBuf
                        
    @staticmethod
    def fromBuf(myBuffer):
        newUsrBin=Usrbin()
        for myLine in myBuffer.split("\n"):
            myLine=myLine.strip()
            if (myLine.startswith("*")):
                newUsrBin.tailMe(myLine)
            elif (myLine.startswith("ROTPRBIN")):
                newUsrBin.assignTrasf(myLine[20:30].strip())
                if (len(newUsrBin.TransfName)==0):
                    print("...something wrong when parsing USRBIN cards: no ROT-DEFI card name!")
                    exit(1)
            else:
                newUsrBin.definition.append(myLine[10:70])
                if (len(newUsrBin.definition)==1):
                    # from first line defining USRBIN, get USRBIN name
                    newUsrBin.rename(myLine[70:].strip(),lNotify=False)
        if (len(newUsrBin.definition)!=2):
            print("...something wrong when parsing USRBIN cards: got %d lines!"\
                  %(len(newUsrBin.definition)))
            exit(1)
        if (len(newUsrBin.name)==0):
            print("...something wrong when parsing USRBIN cards: no name!")
            exit(1)
        return newUsrBin

    def getUnit(self):
        return float(self.definition[0][20:30])
    def setUnit(self,myUnit,lFree=False):
        if (self.getUnit()<0):
            self.definition[0]=self.definition[0][ 0:20]+echoFloats(-abs(myUnit),lFree=lFree)[0]+ \
                               self.definition[0][30:]
        else:
            self.definition[0]=self.definition[0][ 0:20]+echoFloats( abs(myUnit),lFree=lFree)[0]+ \
                               self.definition[0][30:]

    def isSpecialBinning(self):
        binType=int(abs(float(self.definition[0][0:10]))+1E-4)
        return binType==2.0 or binType==12.0 or binType==8.0 or binType==18.0

    def getNbins(self,axes="all"):
        nBins=None
        if (not self.isSpecialBinning() ):
            if (isinstance(axes,list)):
                nBins=1
                for myAx in axes:
                    nBins=nBins*self.getNbins(axes=myAx)
            elif (isinstance(axes,str)):
                if (axes.upper()=="ALL"):
                    nBins=self.getNbins(axes=[1,2,3])
                elif (axes.upper()=="X"):
                    nBins=self.getNbins(axes=[1])
                elif (axes.upper()=="Y"):
                    nBins=self.getNbins(axes=[2])
                elif (axes.upper()=="Z"):
                    nBins=self.getNbins(axes=[3])
                else:
                    print("cannot get number of bins on ax specified as %s!"%(axes))
                    exit(1)
            elif (1<=axes and axes<=3):
                nBins=int(abs(float(self.definition[1][30+(axes-1)*10:40+(axes-1)*10]))+1E-4)
            else:
                print("cannot get number of bins on ax %d [1:3]!"%(axes))
                exit(1)
        return nBins
    def setNbins(self,nBins=[1],axes=[3],lFree=False):
        if (isinstance(axes,float) or isinstance(axes,int)): axes=[axes]
        elif (isinstance(axes,str)):
            if (axes.upper()=="ALL"):
                axes=[1,2,3]
            else:
                print("cannot set nBins to ax %s!"%(axes))
                exit(1)
        if (isinstance(nBins,float) or isinstance(nBins,int)): nBins=[nBins]
        if (len(axes)!=len(nBins)):
            print("len(axes)!=len(nBins)! axes=",axes,"; nBins=",nBins)
            exit(1)
        for myN,myAx in zip(nBins,axes):
            if (myAx<3):
                self.definition[1]=self.definition[1][0:30+10*(myAx-1)]+\
                   echoFloats(myN,lFree=lFree)[0]+self.definition[1][30+10*myAx:]
            elif (myAx>0):
                self.definition[1]=self.definition[1][0:30+10*(myAx-1)]+\
                   echoFloats(myN,lFree=lFree)[0]
            else:
                print("cannot set %d bins to axis %d!"%(myN,myAx))
                exit(1)

    def getExtremes(self,axes=3):
        myMin=None; myMax=None
        if (isinstance(axes,list)):
            myMin=[]; myMax=[]
            for myAx in axes:
                tmpMin,tmpMax=self.getExtremes(axes=myAx)
                myMin.append(tmpMin); myMax.append(tmpMax)
        elif (isinstance(axes,float) or isinstance(axes,int)):
            if (1<=axes and axes<=2):
                myMax=float(self.definition[0][30+(axes-1)*10:30+axes*10])
            elif (axes==3):
                myMax=float(self.definition[0][30+(axes-1)*10:          ])
            else:
                print("cannot get extremes of bin on axis %d!"%(axes))
                exit(1)
            myMin=float(self.definition[1][ (axes-1)*10:axes*10])
        elif (isinstance(axes,str)):
            if (axes.upper()=="X"):
                myMin,myMax=self.getExtremes(self,axes=1)
            elif (axes.upper()=="Y"):
                myMin,myMax=self.getExtremes(self,axes=2)
            elif (axes.upper()=="Z"):
                myMin,myMax=self.getExtremes(self,axes=3)
            else:
                print("cannot get extremes of bin on axis %s!"%(axes))
                exit(1)
        return myMin,myMax
    def setExtremes(self,myMin,myMax,axes=3,lFree=False):
        if (isinstance(myMin,list) and isinstance(myMax,list) and isinstance(axes,list)):
            if (len(myMin)!=len(myMax) or len(myMin)!=len(axes)):
                print("cannot set min=",myMin,",max=",myMax,"axes",axes)
                exit(1)
            for tMin,tMax,tAx in zip(myMin,myMax,axes):
                self.setExtremes(tMin,tMax,axes=tAx)
        elif (not isinstance(myMin,list) and not isinstance(myMax,list) and not isinstance(axes,list)):
            myMinStr=echoFloats(myMin,lFree=lFree)[0]
            myMaxStr=echoFloats(myMax,lFree=lFree)[0]
            if (isinstance(axes,float) or isinstance(axes,int)):
                if (1<=axes and axes<=2):
                    self.definition[0]=self.definition[0][:30+(axes-1)*10]+\
                                       myMaxStr+\
                                       self.definition[0][30+axes*10:]
                elif (axes==3):
                    self.definition[0]=self.definition[0][:30+(axes-1)*10]+\
                                       myMaxStr
                else:
                    print("cannot set extremes of bin on axis %d!"%(axes))
                    exit(1)
                self.definition[1]=self.definition[1][:(axes-1)*10]+\
                                   myMinStr+\
                                   self.definition[1][axes*10:]
            elif (isinstance(axes,str)):
                if (axes.upper()=="X"):
                    self.setExtremes(self,myMin,myMax,axes=1)
                elif (axes.upper()=="Y"):
                    self.setExtremes(self,myMin,myMax,axes=2)
                elif (axes.upper()=="Z"):
                    self.setExtremes(self,myMin,myMax,axes=3)
                else:
                    print("cannot set extremes of bin on axis %s!"%(axes))
                    exit(1)
        else:
            print("mixed arrays!")
            exit(1)

    def resize(self,newL,axis=3):
        if (axis!=3):
            print("For the time being, it is possible to re-size USRBINs only along the Z-axis!")
            exit(1)
        currMin,currMax=self.getExtremes(axes=axis); currNbins=self.getNbins(axes=axis)
        currDelta=currMax-currMin; currStep=currDelta*1.0/currNbins
        currMean=(currMax+currMin)*0.5
        # actually resize
        newNbins=newL*1.0/currDelta*currNbins
        if (newNbins%1<0.5):
            newNbins=int(newNbins)
        else:
            newNbins=int(newNbins)+1
        newMin=currMean-0.5*newNbins*currStep
        newMax=currMean+0.5*newNbins*currStep
        self.setExtremes(newMin,newMax,axes=axis)
        self.setNbins(nBins=newNbins,axes=axis)

    def assignTrasf(self,trasfName):
        if (len(trasfName)>0):
            self.TransfName=trasfName
    def returnTrasf(self):
        return self.TransfName
    
