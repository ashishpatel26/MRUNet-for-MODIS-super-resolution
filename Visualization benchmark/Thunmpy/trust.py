def trust(Image, Emiss, T_mean, Atmo, *args):
	
#   TRUST Code python of the TRUST algorithm
#
#	trust_run(Image, Emiss, T_mean, Atmo) is estimating the
#   abundances S_mix and the subpixel temperatures T_mix using the image
#   Image, the emissivities Emiss and the mean temperature T_mean. It also
#   needs the atmospherical terms Atmo.
#   Input :
#       - Image     : It is the at-sensor radiance in W.sr-1.m-2.�m-1. A 
#       2-dim matrix (npix * nband) or a 3-dim matrix (nlength * nwidth *
#       nband) where nlength * nwidth = npix the number of pixels.
#       - Emiss     : Emissivity of each classes of material composing the
#       scene. The size is (nmat * nband) where nmat is the number of
#       classes of material.
#       - T_mean    : The mean temperature of classes of material in K. It
#       is a vector of nmat elements.
#       - Atmo      : Structure composed by the atmospheric terms
#       (Tup, LatmDown, LatmUp).
#   Output :
#       - S_mix     : The abundances estimated by TRUST. Depending on the
#       size of the input Image, S_mix is a 2-dim matrix (npix * nmat) or
#       a 3-dim matrix (nlength * nwidth * nmat).
#       - T_mix     : The subpixel temperature estimated by TRUST. There is
#       the same size than S_mix.
#   Optional Input :
#       - 'nmat_stop'   : Maximum number of material composing the mixed
#       pixels. If not inquire, nmat_stop = 3.
#       - 'gamma'       : Hyperparameter gamma for the minimization. If not
#       inquire, gamma = 0.
#   Optional Output :
#       "Error" is the RMSE of the reconstruction for all pixels. Depening on the size
#       of Image. "Error" is a 2-dim matrix (npix * nperms) or a 3-dim matrix (nlength *
#       nwidth * nperms). nperms is the number of possible permutations.
# 
#   Reference : M. Cubero-Castan et al., 'A physic-based unmixing method to
#   estimate subpixel temperatures on mixed pixels', TGRS 2015.
#   Manuel Cubero-Castan
#   Revision: 1.0 $  $Date: 2014/07/09$
##
###
######
######### Python Version of Cubero-Castan Matlab code
###########
############### C. Granero-Belinchon; ONERA, Toulouse; 06/2019

# We import the needed python libraries
	import numpy as np
	import scipy.optimize as opt
	from scipy.optimize import LinearConstraint
	import sys
	sys.path.append("/tmp_user/ldota853h/cgranero/Thunmpy/")
	from trust import trust_cest
	from trust import perms_Manu
	
	import warnings
	warnings.filterwarnings("ignore") ##ok<WNOFF>
	### Initialisation
	
	## We read the size of the image
	## We define the 2D size of the image for any 2D or 3D image. We also define the paramer Opt3D indicating 3D image if it's equal to 1.
	## If SizeIm.shape is not 2 or 3 dimensional then there is a problem.
	SizeIm = Image.shape    
	if len(SizeIm) == 2:
		Size2D = SizeIm 
		Im2D = Image 
		Opt3D = 0
	elif len(SizeIm) == 3:	             
		Size2D = [SizeIm[0]*SizeIm[1], SizeIm[2]]
		Im2D = np.reshape(Image,Size2D,order='F')
		Opt3D = 1
	else:
		print('Size Image Problem !!!\n') 
		import sys
		sys.exit()

	### Emiss should be a matrix M x Nmat (Bands times materials)
	if len(Emiss.shape)==1:          # This is a test to avoid python dimensionality problems
		Emiss=Emiss[np.newaxis,:]
	if len(Emiss[0,:]) == Size2D[1]: 
		Emiss = Emiss.T # Transpose of a 2D vector

    ### We define the number of materials Nmat as the dimension of Emiss wich is different to M (Size2D(2)=M=number of bands).
	NMat = len(Emiss[0,:])

    ### Finally, we arrange the Emiss and T_mean arrays to have Nmat as the second dimension.
	if len(T_mean.shape)==1:         # This is a test to avoid python dimensionality problems
		T_mean=T_mean[np.newaxis,:]
	if len(T_mean[:,0]) == NMat: 
		T_mean = T_mean.T 
	
	### Options
	### We define the different possibilities (varargin) arguments of TRUST function.
	### Major Parameters
	### NMat_Stop == Maximum number of materials per pixel ??
	### gamma == hyperparameter for second minimisation taking into account temperature differences
	### Minor parameters
    ### nargout == number of additional outputs
	gamma = 0      # It can take any value
	NMat_Stop = 3  # It should be limited to 3. Cubero-Castan suggestion
	nargout=0
	nargin=len(args)+4
	
	for ind in range(0,nargin-5,2):
		### Major parameters
		if args[ind] == 'nmat_stop': 
			NMat_Stop = args[ind+1]
		elif args[ind] ==	'gamma': 
			gamma = args[ind+1]	
	    ### Minor parameters
		elif args[ind] == 'nargout': 
			nargout = args[ind+1]
	print(NMat_Stop)
	### Initialisation

    ### Permutation
    ### P is a empty matrix of dimension (Nmat,1)
    ### Each element of the matrix P is defined as perms_Manu(i,3), which defines the possible combinations of materials with a maximum of three different materials per pixel.
	P= perms_Manu(NMat,NMat_Stop) 
	nperms=len(P)
	for l in range(0,nperms):
		P_tmp=P[l]
		P_tmp[:]=[x-1 for x in P_tmp]	
	Kl = np.arange(0,NMat)   # As it will be used as index we start in zero.
	### Outputs initialization
	### We initialize the result arrays S_mix (abondances =  pixels times materials matrix) and T_mix (temperatures = pixels times materials matrix)
	S_mix = np.zeros((Size2D[0],NMat))    
	T_mix = np.zeros((Size2D[0],NMat))
	T_mix[:]=np.nan
	
	### Else Err == a nan matrix of dimension (npixels x  possible combinations of three NMat materials)    
	Err = np.zeros((Size2D[0],nperms))
	Err[:]=np.nan
		
	### Non nan pixels search
	### We look for the pixels where at least in one band have nan values. Ind == all the other pixels
	tmp = np.sum(Im2D,axis=1)  
	tmp=tmp[np.newaxis,:]
	tmp=tmp.T
	Ind = np.where(~np.isnan(tmp))
	Ind=Ind[0]
	### Loop over the non nan pixels
	### i goes from 1 to the number of non nan pixels in the image. x is the coordinates of the non nan pixels
	x=np.zeros((2,1))
	for i in range(0,len(Ind)):    
		x = Ind[i]
		x=x.astype(int)	
		print('x={} in {}/{}'.format(x,i,len(Ind)))
		try:
			### Vectors' Initialisation
			D_Vect = np.zeros((nperms,1))         # Reconstruction error
			D_Vect[:] = np.nan
			T_Vect = np.zeros((nperms,NMat))      # Temperature vector
			T_Vect[:] = np.nan
			S_Vect = np.zeros((nperms,NMat))    # Abondance vector
			
			for l in range(0,nperms):
				#print('l=',l)
				Cc = P[l]
				#print('Cc=',Cc)  
				N_cc = len(Cc)
				#print(Emiss[:,Cc], T_mean[:,Cc])
				## Minimization S with CEST
				S_2 = opt.minimize(lambda S: trust_cest(S, Im2D[x,:], Emiss[:,Cc], T_mean[:,Cc], Atmo, 'gamma', 0,'nargout',0), (1/N_cc)*np.ones((N_cc)), constraints = LinearConstraint(np.ones((N_cc)), 1, 1), bounds=opt.Bounds(0.01, 0.99), method='trust-constr')
				[DD,TT] = trust_cest(S_2.x, Im2D[x,:], Emiss[:,Cc], T_mean[:,Cc], Atmo, 'gamma', gamma,'nargout',1)
				S_Vect[l,Cc] = S_2.x
				D_Vect[l]=DD
				T_Vect[l,Cc]=TT
				#print(S_2.x,TT,DD)
				if sum(S_Vect[l,Cc]<0)>0: 
					D_Vect[l]=np.nan
	        ### Search of the best reconstruction
			Num=np.argmin(D_Vect,0) # Array of indices with minimum values along axis 0
			#print(Num)
			T_mix[x,:]  = T_Vect[Num,:]
			S_mix[x,:]  = S_Vect[Num,:]
			Err[x,0:nperms]  = D_Vect[:].T
		except:
			print('# = %d\n',i) 
			T_mix[x,:]=np.nan 
			S_mix[x,:]=np.nan  ##ok<CTCH>
	
	### Reshape of the image to the original shape
	### The outputs of the function are S_mix and T_mix with the shapes of the input image times NMat (number of materials).
	if Opt3D==1: 
		S_mix = np.reshape(S_mix,(int(SizeIm[0]),int(SizeIm[1]),int(NMat)),order='F')    
		T_mix = np.reshape(T_mix,(SizeIm[0],SizeIm[1],NMat),order='F') 
		Err = np.reshape(Err,(SizeIm[0],SizeIm[1],nperms),order='F')
	if NMat_Stop == 1: 
		if Opt3D==1: 
			S_mix = np.reshape(S_mix,(Size2D[0],NMat),order='F')
		C = np.zeros((1,Size2D[1]))
		for b in range(0,NMat): 
			C[:] = C[:] + b * (S_mix[:,b]==1)
		C[C==0]=np.nan
		if Opt3D==1: 
			S_mix = np.reshape(C,(SizeIm[0],SizeIm[1]),order='F') 
		else: 
			S_mix=C
    ### If we ask for more than two outputs, we can obtain the error per pixel.
	if nargout>2:                                
		varargout = Err
		return S_mix,T_mix,varargout
	return S_mix,T_mix

def trust_cest(S_tmp,Lsens,Emiss2,Temp,Atmo,*args):
	
#   TRUST_CEST Python Code of the Constrain Estimation of Subpixel Temperature
#
#	trust_cest(S_tmp, Lsens, Emiss, Temp, Atmo) is estimating the
#	error Diff when the subpixel temperature is retrieved. S_tmp is the
#	input abundance, Lsens the at-sensor radiance, Emiss the emissivity of
#	the classes of materials composing the mixed pixels, Temp the mean
#	temperature of the classes of materials and Atmo the atmospheric terms
#	structure.
# 
#   Input :
#       - S_tmp     : The input abundance. A vector of size (nmat * 1) 
#       where nmat is the number of classes of material.
#       - Lsens     : The input at-sensor radiance in W.sr-1.m-2.�m-1. A
#       vector of size (1 * nband) where nband is the number of spectral
#       bands.
#       - Emiss     : Emissivity of each classes of material composing the
#       pixel. The size is (nband * nmat).
#       - Temp      : The mean temperature of each classes of material. The
#       size is (nmat * 1).
#       - Atmo      : Structure composed by the atmospheric terms
#       (Tup, LatmDown, LatmUp).
#   Optional Input :
#       - 'gamma'   : Hyperparameter gamma for the minimization. If not
#       inquire, gamma = 0.
#       - 'noise_inv' : If the Noise Covariance matrix 'C' is known. If
#       it is not inquire, C = eye(nband).
#       - 'nargout' : number of additional outputs
#   Output :
#       - Diff      : The cost function linked the RMSE of the reconstruc-
#       tion and the physical constrain on temperature with the hyper-
#       parameter gamma.
#   Optional Output :
#       T_mix is the subpixel temperature in K.
#       CN is the Condition Number of the estimation, without dimension.
#       CRLB is the Cramer-Rao lower bound, in K�.
#
#   Reference : M. Cubero-Castan et al., 'An unmixing-based method for the
#   analysis of thermal hyperspectral images', ICASSP 2014.
#   Copyright 2014 ONERA - MCC PhD
#   Manuel Cubero-Castan
#   $Revision: 1.0 $  $Date: 2014/07/09$	
###
#####
####### 
######### Python Version of Cubero-Castan Matlab code
###########
############# Granero-Belinchon, Carlos;  ONERA, Toulouse; 06/2019

# We import the python libraries
	import numpy as np
	import scipy.linalg as la
	import sys
	sys.path.append("/tmp_user/ldota214h/cgranero/Codes_Manu/function")
	from trust import Lcn
	from trust import DLcn
	
	S_tmp=np.array(S_tmp)
	if len(S_tmp.shape)==1:          # This is a test to avoid python dimensionality problems
		S_tmp=S_tmp[:,np.newaxis]
	
	### Atmosphere terms
	Ld = Atmo[3][1,:] 
	Lu = Atmo[1][1,:] 
	Tu = Atmo[0][1,:]
	Wave = Atmo[0][0,:]  
	NWave = len(Wave) 
	if len(Emiss2.shape)==1:          # This is a test to avoid python dimensionality problems
		Emiss2=Emiss2[:,np.newaxis]
	NMat = len(Emiss2[0,:])
	
	### Study of varargin
	gamma = 0
	C = np.identity(NWave);
	
	nargin=len(args)+5
	
	for ind in range(0,nargin-5,2):
		if args[ind]=='gamma':
			gamma = args[ind+1]
		elif args[ind]=='noisecorr_inv':
			C = args[ind+1]
		elif args[ind]=='nargout':
			nargout = args[ind+1]
				
	### Build LcnMat & DLcnMat
	LcnMat = Lcn(Wave,Temp) 
	DLcnMat = DLcn(Wave,Temp)
	### Inversion Temperature (section 4.3.1 Cubero-Castan Thesis)
	Lsens_tmp = np.sum( Emiss2.T * LcnMat * (S_tmp*Tu) + (1-Emiss2.T) * (np.ones((NMat,1))*Ld) * S_tmp + (S_tmp*Lu),axis=0)
	B = (Lsens.T - Lsens_tmp.T)
	A = (np.transpose(Tu)*np.ones((NMat,1))) * np.transpose(Emiss2) * (np.ones((1,NWave))*S_tmp) * DLcnMat
	Mfish = np.matmul(np.matmul(A,C),A.T)
	temporal=la.solve(Mfish,np.matmul(np.matmul(A,C),B))
	T = Temp + temporal.T  
	
	### LsensNew estimation (with the temperature obtained in the above lines)
	LcnMat = Lcn(Wave,T)
	Lsens_tmp = np.sum( Emiss2.T * LcnMat * (S_tmp*Tu) + (1-Emiss2.T) * (np.ones((NMat,1))*Ld) * S_tmp + (S_tmp*Lu),axis=0)
	
	### Difference with the inputs (section 4.4.2 Cubero-Castan Thesis)
	Diff = np.sqrt(np.mean((Lsens_tmp - Lsens)**2)) + gamma * np.sqrt(np.mean((T-Temp)**2))
	
	### Study of varargout : 1 = Temperature, 2 = Condition Number
	if nargout != 0:
		varargout=np.zeros((nargout,len(T[:,0]),len(T[0,:])))
		if nargout >= 1:
			varargout[0] = T
		### Construction of the CN
		if nargout >= 2: 
			tmp2,tmp = la.eig(Mfish) 
			varargout[1] = max(tmp)/min(tmp)
		if nargout == 3: 
			varargout[2] = np.diag(inv(Mfish))
	
		return Diff,varargout 
		
	return Diff

### List -  
def funct_List(list_1,Nmat):
	### size(list_1) = [Nnum,Ntest]
	###     - Nnum = nombre de matériau présent
	###     - Ntest = nombre de test à effectuer
	### Example 1 :
	### list_1 = 1;2;4
	### list_2 = 5
	###     ==> List' = [1,1,1,1,2,2,2,4,4;
	###                 2,3,4,5,3,4,5,3,5];
	### Example 2 :
	### list_1 = 1,2
	### list_2 = 5
	###     ==> List' = [1,1,1;
	###                 2,2,2;
	###                 3,4,5];
	#perms_Manu(Nmat)
#list_1=np.array(([1],[2],[4]))
#list_1=np.array((1,2))
###
#####
####### 
######### Python Version of Cubero-Castan Matlab code
###########
############# Granero-Belinchon, Carlos;  ONERA, Toulouse; 06/2019

	import numpy as np

	lshap = list_1.shape
	if len(lshap)==1:
		list_1=list_1[np.newaxis,:]
		lshap = list_1.shape
	Nnum  = lshap[1]
	Ntest = lshap[0]
	NList = Ntest * (Nmat - Nnum)
	List = np.zeros((NList,Nnum+1))
	for ind in range(0,Ntest):
		List[(ind)*(Nmat - Nnum):(ind+1)*(Nmat - Nnum),0:Nnum] = np.ones(((Nmat - Nnum),1)) * list_1[ind,:]
		List[(ind)*(Nmat - Nnum):(ind+1)*(Nmat - Nnum),Nnum] = np.setdiff1d(range(1,Nmat+1),list_1[ind,:])
	
	List_tmp = np.sort(List,axis=1)
	[non,tmp] = np.unique(List_tmp,axis=0,return_index=True)
	List = List[tmp,:]
	tmp = np.argsort(List[:,0],axis=0)  
	List = List[tmp,:]

	return List
	
def perms_Manu(Nmat, *args):
# switch Nmat
#     case 1
#         C = {1};
#     case 2
#         C = {1; 2; [1,2]};
#     case 3
#         C = {1; 2; 3; [1,2]; [1,3]; [2,3]; [1,2,3]};
#     case 4
#         C = {1; 2; 3; 4; [1,2]; [1,3]; [1,4]; [2,3]; [2,4]; [3,4];...
#             [1,2,3]; [1,2,4]; [1,3,4]; [2,3,4]; [1,2,3,4]};
#     case 5
#         C = {1; 2; 3; 4; 5; ...
#             [1,2]; [1,3]; [1,4]; [1,5]; [2,3]; [2,4]; [2,5]; [3,4]; ...
#                 [3,5]; [4,5]; ...
#             [1,2,3]; [1,2,4]; [1,2,5]; [1,3,4]; [1,3,5]; [1,4,5]; ...
#                 [2,3,4]; [2,3,5]; [2,4,5]; [3,4,5]; ...
#             [1,2,3,4]; [1,2,3,5]; [1,2,4,5]; [1,3,4,5]; [2,3,4,5]};
# end

###
#####
####### 
######### Python Version of Cubero-Castan Matlab code
###########
############# Granero-Belinchon, Carlos;  ONERA, Toulouse; 06/2019

	import numpy as np
	import scipy.special as sp
	import pandas as pd
	import sys
	#sys.path.append("/tmp_user/ldota853h/cgranero/Codes_Manu/function")
	from trust import combn
	
	Nlength = 3
	if len(args) >=1: 
		Nlength = args[0]
	
	S_tot = 0 
	for i in range(1,min(Nmat,Nlength)+1):
		S_tot = S_tot + sp.comb(Nmat,i)
		
	C = list(np.zeros((int(S_tot),1))) 
	
	it=0
	for i in range(1, min(Nmat,Nlength)+1):
		tmp,tmp2 = combn(np.arange(1,Nmat+1),i)
		if len(tmp.shape)==1:
			tmp=tmp[np.newaxis,:]
		tmp = np.sort(tmp,axis=1)
		tmp = np.unique(tmp,axis=0)
		for j in range(0,len(tmp)):  # len of the first dimension '0'
			temp=np.unique(tmp[j,:])
			if len(temp.shape)==1:
				temp=temp[np.newaxis,:]
			if len(temp[0,:])==i:
				C0 = list(tmp[j,:]) 
				C[it]=C0
				it=it+1
	return C

def combn(V,N):
#	
###
#####
####### 
######### Python Version of Cubero-Castan Matlab code
###########
############# Granero-Belinchon, Carlos;  ONERA, Toulouse; 06/2019
	
	import numpy as np
	import sys
	sys.path.append("/tmp_user/ldota214h/cgranero/Codes_Manu/function")
	from trust import local_allcomb
	
	if V.size==0 or N == 0:
		M = [] 
		IND = [] 
	elif np.fix(N) != N or N < 1 or np.size(N) != 1:
		print('combn:negativeN','Second argument should be a positive integer') 
	elif N==1:
		# return column vectors
		M = V.flatten()
		M=M[np.newaxis,:]
		M=M.T 
		IND = np.matrix(range(0,np.size(V))).getT()
	else:
		# indices requested
		IND = local_allcomb(np.arange(0,np.size(V)),N)
		IND=IND.astype(int)
		M = V[IND]
			
	return M,IND
	
def local_allcomb(X,N):
#
###
#####
####### 
######### Python Version of Cubero-Castan Matlab code
###########
############# Granero-Belinchon, Carlos	;  ONERA, Toulouse; 06/2019
	
	import numpy as np
	from itertools import combinations_with_replacement
	from itertools import permutations
	
	# See ALLCOMB, available on the File Exchange
	if N>1:
		# create a list of all possible combinations of N elements
		#[Y] = np.meshgrid(X) 
		comb = combinations_with_replacement(X,N)
		Y=list(comb)
		YY1=[]
		for i in range(len(Y)):
			perm = permutations(Y[i])
			YY2=list(perm)
			YY1=np.append(YY1,YY2)
		
		Y=YY1[::-1]
		# concatenate into one matrix, reshape into 2D and flip columns
		Y = np.reshape(YY1.flatten(),(-1,N))
		Y= np.unique(Y,axis=0)
	else:
		# no combinations have to be made
		Y = X.flatten()
		
	return Y

def Lcn(lambdas,T):
    ### Black Body function on python.
    # # input   - T         = temperature
    # #         - lambdas    = wavelength
    # # output  - lum       = B^{lambda}({T})
    ### Units : W.m-2.sr-1.µm-1
#
###
#####
#######
######### Python Version of Cubero-Castan Matlab code
###########
############# Granero-Belinchon, Carlos    ;  ONERA, Toulouse; 06/2019
    
    # Verified Function
    import numpy as np
    ### Black Body Law parameters
    C1 = 1.1904e8
    C2 = 1.4388e4
    ### Initialization of variables
    lambdas=np.array(lambdas)
    T=np.array(T)
    
    ### lambda conditionning
    if lambdas.shape ==():
        l_mat=lambdas
    else:
        if len(lambdas.shape)==1:          # This is a test to avoid python dimensionality problems
            lambdas=lambdas[np.newaxis,:]
        if lambdas.shape[1] == 1 and lambdas.shape[0] != 1:
            lambdas = lambdas.T
        l_mat = np.ones((T.size,1)) * lambdas

    ### Temperature conditionning
    if T.shape ==():
        t_mat=T
    else:
        if len(T.shape)==1:          # This is a test to avoid python dimensionality problems
            T=T[np.newaxis,:]
        if T.shape[0] == 1 and T.shape[1] != 1:
            T = T.T
        t_mat = T * np.ones((1,lambdas.size))

    ### Radiance estimation
    lum = C1/((l_mat**5)*(np.exp(C2/(l_mat*t_mat))-1))

    return lum


def DLcn(lambdas,T):
    
    ### Black Body function on matlab.
    # # input   - T         = temperature
    # #         - lambdas    = wavelength
    # # output  - lum       = B^{lambda}({T})
    ### Units : W.m-2.sr-1.µm-1
#
###
#####
#######
######### Python Version of Cubero-Castan Matlab code
###########
############# Granero-Belinchon, Carlos    ;  ONERA, Toulouse; 06/2019
    
    #This function has been verified
    import numpy as np
    
    ### Black Body Law parameters
    C1 = 1.1904e8
    C2 = 1.4388e4
    
    ### Initialization of variables
    lambdas=np.array(lambdas)
    T=np.array(T)
    
    ### lambda conditionning
    if lambdas.shape ==():
        l_mat=lambdas
    else:
        if len(lambdas.shape)==1:          # This is a test to avoid python dimensionality problems
            lambdas=lambdas[np.newaxis,:]
        if lambdas.shape[1] == 1 and lambdas.shape[0] != 1:
            lambdas = lambdas.T
        l_mat = np.ones((T.size,1)) * lambdas

    ### Temperature conditionning
    if T.shape ==():
        t_mat=T
    else:
        if len(T.shape)==1:          # This is a test to avoid python dimensionality problems
            T=T[np.newaxis,:]
        if T.shape[0] == 1 and T.shape[1] != 1:
            T = T.T
        t_mat = T * np.ones((1,lambdas.size))

    #### Radiance estimation
    lum = (C1/l_mat**5) * (C2/(l_mat*t_mat**2)) * np.exp(C2/(l_mat*t_mat)) * (1/(np.exp(C2/(l_mat*t_mat))-1)**2)

    return lum
