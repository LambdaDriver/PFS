# encoding: UTF-8
#
# PhotoFilmStrip - Creates movies out of your pictures.
#
# Copyright (C) 2011 Jens Goepfert
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

import os
import sys

from photofilmstrip.action.IAction import IAction

from photofilmstrip.lib.Settings import Settings
from photofilmstrip.core.OutputProfile import GetOutputProfiles
from photofilmstrip.core.Renderer import RENDERERS
from photofilmstrip.lib.util import Encode
from photofilmstrip.core.RenderEngine import RenderEngineSlideshow,\
    RenderEngineTimelapse


class ActionRender(IAction):
    
    def __init__(self, photoFilmStrip, 
                 profile, videoNorm, 
                 rendererClass, draftMode,
                 outpath=None):
        self.__photoFilmStrip = photoFilmStrip
        self.__profile = profile
        self.__profile.SetVideoNorm(videoNorm)
        self.__rendererClass = rendererClass
        self.__draftMode = draftMode
        self.__outpath = outpath
        
        self.__renderJob = None
    
    def GetName(self):
        return _(u'Start')
    
    def CheckFile(self, filename):
        if filename and not os.path.exists(filename):
            return False
        else:
            return True
    
    def _CheckAndGetOutpath(self):
        if self.__outpath == "-":
            return
        
        outpath = os.path.dirname(self.__photoFilmStrip.GetFilename())
        outpath = os.path.join(outpath, self.__profile.GetName())
        outpath = Encode(outpath, sys.getfilesystemencoding())
        if not os.path.exists(outpath):
            os.makedirs(outpath)
        return outpath
    
    def _SaveSettings(self):
        settings = Settings()
        outputProfiles = GetOutputProfiles(self.__photoFilmStrip.GetAspect())
        idxProfile = 0
        for idx, prof in enumerate(outputProfiles):
            if prof.GetName() == self.__profile.GetName():
                idxProfile = idx
        settings.SetLastProfile(idxProfile)
        
        settings.SetVideoType(self.__profile.GetVideoNorm())
        
        idxRenderer = RENDERERS.index(self.__rendererClass)
        settings.SetUsedRenderer(idxRenderer)
    
    def Execute(self):
        audioFiles = []
        for audioFile in self.__photoFilmStrip.GetAudioFiles():
            if self.CheckFile(audioFile):
                audioFiles.append(Encode(audioFile, sys.getfilesystemencoding()))

        outpath = self._CheckAndGetOutpath()
        
        self._SaveSettings()
        
        savedProps = Settings().GetRenderProperties(self.__rendererClass.__name__)
        for prop in self.__rendererClass.GetProperties():
            value = savedProps.get(prop.lower(), self.__rendererClass.GetProperty(prop))
            self.__rendererClass.SetProperty(prop, value)
        
        totalLength = self.__photoFilmStrip.GetDuration(False)
        
        renderer = self.__rendererClass()
        renderer.Init(self.__profile, 
                      self.__photoFilmStrip.GetAspect(),
                      outpath)
        
        renderer.SetAudioFiles(audioFiles)

        name = "%s (%s)" % (self.__photoFilmStrip.GetName(),
                            self.__profile.GetName())
        
        if self.__photoFilmStrip.GetTimelapse():
            renderEngine = RenderEngineTimelapse(name,
                                                 renderer,
                                                 self.__draftMode)
        else:
            renderEngine = RenderEngineSlideshow(name,
                                                 renderer,
                                                 self.__draftMode,
                                                 totalLength)

        self.__renderJob = renderEngine.CreateRenderJob(
                self.__photoFilmStrip.GetPictures()
        )

    def GetRenderJob(self):
        return self.__renderJob
