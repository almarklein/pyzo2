from PyQt4 import QtCore, QtGui
import iep
import os.path
import ssdf
import fnmatch

tool_name = "Project manager"
tool_summary = "Manage project directories."

class Project(ssdf.Struct):
    def __init__(self,name,path):
        self.name=name
        self.path=path
    def __repr__(self):
        return "Project %s at %s" % (self.name,self.path)

class ProjectsModel(QtCore.QAbstractListModel):
    def __init__(self,config):
        QtCore.QAbstractListModel.__init__(self)
        self.config=config
    def rowCount(self,parent):
        return len(self.config.projects)
    def data(self, index, role):
        if not index.isValid():
            return None
             
        if role == QtCore.Qt.DisplayRole:
            return self.projectFromIndex(index).name
        elif role == QtCore.Qt.UserRole:
            return self.projectFromIndex(index)
    def setData(self,index,value,role):
        """Change the name of a project"""
        if not index.isValid():
            return False
        if role == QtCore.Qt.EditRole:
            self.projectFromIndex(index).name=value
            self.dataChanged.emit(index,index)
            return True
        return False
    def supportedDropActions(self):
        return QtCore.Qt.MoveAction
    def flags(self,index):
        if not index.isValid():
            return QtCore.Qt.ItemIsEnabled
        else:
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | \
                QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsDragEnabled | \
                QtCore.Qt.ItemIsDropEnabled
                
    def add(self,project):
        self.config.projects.append(project)
        self.reset()
        return self.config.projects.index(project)
    def remove(self,project):
        self.config.projects.remove(project)
        self.reset()
    def projectFromIndex(self,index):
        return self.config.projects[index.row()]
    def projectFromRow(self,row):
        if row<0 or row>=len(self.config.projects):
            return None
        return self.config.projects[row]
    def swapRows(self,row1,row2):
        if row1==row2:
            return
            
        #Ensure row1<row2
        if row2>row1:
            row1,row2=row2,row1
            
        self.beginMoveRows(QtCore.QModelIndex(),row1,row1,QtCore.QModelIndex(),row2)
        project1=self.config.projects[row1]
        self.config.projects[row1]=self.config.projects[row2]
        self.config.projects[row2]=project1
        self.endMoveRows()


class ProjectsList(QtGui.QListView):
    def __init__(self):
        QtGui.QListView.__init__(self)
        self.draggingRow=None
    def mouseMoveEvent(self,event):
        """
        If the user drags an item, swap rows if necessary
        """
        pos=event.pos()
        index=self.indexAt(pos)
        if not index.isValid():
            return
        
        #Find ot the new position of the row
        rect=self.visualRect(index)
        newRow=index.row()
        if pos.y()>rect.y()+rect.height()/2:
            #Below the horizontal center line of the item
            newRow+=1
        if newRow>self.draggingRow:
            #Moving below the original position
            newRow-=1
            
        if newRow!=self.draggingRow:
            self.model().swapRows(newRow,self.draggingRow)
            self.draggingRow=newRow
    def mousePressEvent(self,event):
        """Register at which row a drag operation starts"""
        self.draggingRow=self.indexAt(event.pos()).row()
        QtGui.QListView.mousePressEvent(self,event) 


class FileFilter(QtGui.QSortFilterProxyModel):
    """
    Proxy model to filter a directory tree based on filename patterns
    """
    def __init__(self):
        QtGui.QSortFilterProxyModel.__init__(self)
        self.filter='!*.pyc'
    def filterAcceptsRow(self,sourceRow,sourceParent):
        #Overridden method to determine wether a row should be
        #shown or not. Check wether the item matches the filter
        
        #Get the fileinfo of the item
        item=self.sourceModel().index(sourceRow,0,sourceParent)
        fileInfo=self.sourceModel().fileInfo(item)
        
        #Show everything that's not a file
        if not fileInfo.isFile():
            return True
        
        fileName=fileInfo.fileName()
        
        #'default' is the return value when no filter matches. A 'hide' filter
        #(i.e. starting with '!') sets the default to 'show', a 'show' filter
        #(i.e. not starting with '!') sets the default to 'hide'
        
        default=True #Return True if there are no filters
                
        #Get the current filter spec and split it into separate filters
        filters=self.filter.replace(',',' ').split()          
        for filter in filters:
            #Process filters in order
            if filter.startswith('!'):
                #If the filename matches a filter starting with !, hide it
                if fnmatch.fnmatch(fileName,filter[1:]):
                    return False
                default=True
            else:
                #If the file name matches a filter not starting with!, show it
                if fnmatch.fnmatch(fileName,filter):
                    return True
                default=False
                    
        #No filter matched, return True
        return default
        
    def setFilter(self,filter):
        """Set and apply the filter"""
        self.filter=filter
        self.invalidateFilter()
        
        

class IepProjectManager(QtGui.QWidget):
    def __init__(self,parent):
        QtGui.QWidget.__init__(self,parent)
        
        # Init config
        toolId =  self.__class__.__name__.lower()
        self.config = iep.config.tools[toolId]
        if not hasattr(self.config, 'projects'):
            self.config.projects=[]
        if not hasattr(self.config,'activeproject'):
            self.config.activeproject=-1
        if not hasattr(self.config,'filter'):
            self.config.filter='!*.pyc'
        if not hasattr(self.config,'listdisclosed'):
            self.config.listdisclosed=True
        
        #Init projects model
        self.projectsModel=ProjectsModel(self.config)

        #Init dir model and filtered dir model
        self.dirModel=QtGui.QDirModel()       
        self.dirModel.setSorting(QtCore.QDir.DirsFirst)
        self.filteredDirModel=FileFilter()
        self.filteredDirModel.setSourceModel(self.dirModel)
                
        #Init widgets and layout
        self.buttonLayout=QtGui.QVBoxLayout()
        self.listDisclosureButton=QtGui.QPushButton('...')
        self.listDisclosureButton.setCheckable(True)
        
        #The following two buttons are only added when the list is disclosed
        self.addProjectButton=QtGui.QPushButton('+')
        self.removeProjectButton=QtGui.QPushButton('-')
        
        self.buttonLayout.addWidget(self.listDisclosureButton,0)
        self.buttonLayout.addStretch(1)

        self.projectsCombo=QtGui.QComboBox()
        self.projectsCombo.setModel(self.projectsModel)
        
        self.hLayout=QtGui.QHBoxLayout()
        self.hLayout.addWidget(self.projectsCombo,1)
        self.hLayout.addLayout(self.buttonLayout,0)
  
        self.projectsList=ProjectsList()
        self.projectsList.setModel(self.projectsModel)
        
        self.dirList=QtGui.QTreeView()
        self.filterCombo=QtGui.QComboBox()

        self.layout=QtGui.QVBoxLayout()
        self.layout.addLayout(self.hLayout)
        self.layout.addWidget(self.dirList,10)
        self.layout.addWidget(self.filterCombo)
        
        self.setLayout(self.layout)
        
        #Load projects in the list
        self.projectsCombo.show()
        
        #Load default filters
        self.filterCombo.setEditable(True)
        self.filterCombo.setCompleter(None)
        self.filterCombo.setInsertPolicy(self.filterCombo.NoInsert)
        for pattern in ['*', '!*.pyc','*.py *.pyw *.pyx *.pxd', '*.h *.c *.cpp']:
            self.filterCombo.addItem(pattern)
        
        # Set file pattern line edit (in combobox)
        self.filterPattern = self.filterCombo.lineEdit()
        self.filterPattern.setText(self.config.filter)
        self.filterPattern.setToolTip('File filter pattern')        

        #Connect signals
        self.projectsCombo.currentIndexChanged.connect(self.comboChangedEvent)
        self.projectsList.selectionModel().currentChanged.connect(self.listChangedEvent)
        self.dirList.doubleClicked.connect(self.itemDoubleClicked)
        self.filterCombo.editTextChanged.connect(self.filterChanged)
        self.listDisclosureButton.toggled.connect(self.listDisclosed)
        self.addProjectButton.clicked.connect(self.addProjectClicked)
        self.removeProjectButton.clicked.connect(self.removeProjectClicked)
        
        #Apply previous selected project
        self.projectChanged(self.config.activeproject)
        if self.config.listdisclosed:
            self.listDisclosureButton.toggle()
        
    ## Project changed handlers
    def comboChangedEvent(self,newIndex):
        self.projectChanged(newIndex)
            
    def listChangedEvent(self,current,previous):
        if not current.isValid():
            self.projectChanged(-1)
        else:
            self.projectChanged(current.row())
        
    def projectChanged(self,projectIndex):
        """Handler for when the project is changed
        projectIndex: -1 or None for no project or 0..len(projects)
        """
        if projectIndex==-1 or projectIndex is None:
            #This happens when the model is reset
            self.dirList.setModel(None)
            return
        
        #Remember the previous selected project
        self.config.activeproject=projectIndex
  
        #Sync list and combo boxes
        self.projectsCombo.setCurrentIndex(projectIndex)
        self.projectsList.selectionModel().setCurrentIndex(self.projectsModel.index(projectIndex), 
                QtGui.QItemSelectionModel.ClearAndSelect)
    
        #Sync the dirList
        project=self.projectsModel.projectFromRow(projectIndex)
        if project is None:
            return #Invalid project index
    
        path=project.path
    
        self.dirList.setModel(self.filteredDirModel)
        self.dirList.setColumnHidden(1,True)
        self.dirList.setColumnHidden(2,True)
        self.dirList.setColumnHidden(3,True)
        
        self.dirList.setRootIndex(self.filteredDirModel.mapFromSource(self.dirModel.index(path)))
 
    ## Add/remove buttons
    def addProjectClicked(self):
        dir=QtGui.QFileDialog.getExistingDirectory(None,'Select project directory')
        if dir=='':
            return #Cancel was pressed
        _,projectName=os.path.split(dir)
        index=self.projectsModel.add(Project(projectName,dir))
        self.projectChanged(index)
        
    def removeProjectClicked(self):
        if not self.projectsList.currentIndex().isValid():
            return
        
        projectIndex=self.projectsList.currentIndex()
        projectRow=projectIndex.row()
        project=self.projectsModel.projectFromIndex(projectIndex)
  
        confirm=QtGui.QMessageBox(QtGui.QMessageBox.Warning,
            "Remove project?",
            "Remove project '%s'?" % project.name)
            
        confirm.addButton("Remove",QtGui.QMessageBox.DestructiveRole)
        cancel=confirm.addButton("Cancel",QtGui.QMessageBox.RejectRole)
        confirm.setDefaultButton(cancel)
        confirm.setEscapeButton(cancel)
        
        confirm.setInformativeText("The project contents will not be removed.")
        confirm.exec_()
        
        if confirm.result()!=0: #Cancel button pressed
            return
        
        
        self.projectsModel.remove(project)
        
        #Select another project (try the one before)
        if projectRow>0:
            projectRow-=1
            
        if self.projectsModel.projectFromRow(projectRow) is None:
            #If we deleted the last project
            projectRow=-1

        self.projectChanged(projectRow)

    def listDisclosed(self):
        """Handler for when disclosure button toggled"""
        if self.listDisclosureButton.isChecked():   
            self.hLayout.insertWidget(0,self.projectsList,1)
            self.hLayout.removeWidget(self.projectsCombo)
            self.buttonLayout.addWidget(self.addProjectButton,0)
            self.buttonLayout.addWidget(self.removeProjectButton,0)
            self.projectsCombo.hide()
            self.projectsList.show()
            self.addProjectButton.show()
            self.removeProjectButton.show()
        else:
            self.hLayout.insertWidget(0,self.projectsCombo,1)
            self.hLayout.removeWidget(self.projectsList)
            self.projectsList.hide()
            self.buttonLayout.removeWidget(self.addProjectButton)
            self.buttonLayout.removeWidget(self.removeProjectButton)
            self.addProjectButton.hide()
            self.removeProjectButton.hide()
            self.projectsCombo.show()
            
        self.config.listdisclosed=self.listDisclosureButton.isChecked()
        
    
    def filterChanged(self):
        """Handler for when the filter is changed"""
        filter=self.filterCombo.lineEdit().text()
        self.config.filter=filter
        self.filteredDirModel.setFilter(filter)
        
   
    def itemDoubleClicked(self,item):
        """Handler for if an item is double-clicked"""
        info=self.dirModel.fileInfo(self.filteredDirModel.mapToSource(item))
        if info.isFile():
            #TODO: check extension associations
            if info.suffix() in ['py','c','pyw','pyx','pxd','h','cpp','hpp']:
                iep.editors.loadFile(info.absoluteFilePath())
