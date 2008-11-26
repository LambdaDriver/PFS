#
# PhotoFilmStrip - Creates movies out of your pictures.
#
# Copyright (C) 2008 Jens Goepfert
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

import Image

from core.Subtitle import SubtitleSrt


class RenderEngine(object):
    
    def __init__(self, aRenderer, progressHandler):
        self.__aRenderer = aRenderer
        self.__profile = aRenderer.GetProfile()
        self.__progressHandler = progressHandler
        self.__errorMsg = None

        self.__audioFile = None
        self.__transDuration = 1.0
        self.__picCountFactor = 1.0
        
    def __ComputePath(self, pic):
        px1, py1 = pic.GetStartRect()[:2]
        w1, h1 = pic.GetStartRect()[2:]
        
        px2, py2 = pic.GetTargetRect()[:2]
        w2, h2 = pic.GetTargetRect()[2:]
        
        cx1 = (w1 / 2.0) + px1
        cy1 = (h1 / 2.0) + py1

        cx2 = (w2 / 2.0) + px2
        cy2 = (h2 / 2.0) + py2
        
        pics = self.__GetPicCount(pic)
        
        dx = (cx2 - cx1) / (pics - 1)
        dy = (cy2 - cy1) / (pics - 1)
        dw = (w2 - w1) / (pics - 1)
        dh = (h2 - h1) / (pics - 1)
        
        pathRects = []
        for step in xrange(int(pics)):
            px = cx1 + step * dx
            py = cy1 + step * dy
            width = w1 + step * dw
            height = h1 + step * dh
            
            rect = (px - width / 2.0, 
                    py - height / 2.0, 
                    width, 
                    height)
            
            pathRects.append(rect)
        return pathRects
    
    def __GetPicCount(self, pic):
        """
        returns the number of pictures
        """
        return ((pic.GetDuration() * self.__profile.PFramerate) * self.__picCountFactor) + \
               self.__GetTransCount()
    
    def __GetTransCount(self):
        """
        returns the number of pictures needed for the transition
        """
        return int(self.__transDuration * self.__profile.PFramerate)

    def __CheckAbort(self):
        if self.__progressHandler.IsAborted():
            self.__aRenderer.ProcessAbort()
            return True
        return False
    
    def __ProcAndFinal(self, image, pathRects):
        for rect in pathRects:
            if self.__CheckAbort():
                return False
            
            self.__progressHandler.Step()
            img = self.__aRenderer.ProcessCropAndResize(image,
                                                        rect, 
                                                        self.__profile.PResolution)
            self.__aRenderer.ProcessFinalize(img)
        return True

    def __TransAndFinal(self, imgFrom, imgTo, pathRectsFrom, pathRectsTo):
        if len(pathRectsFrom) != len(pathRectsTo):
            raise RuntimeError
        
        COUNT = len(pathRectsFrom)
        
        for idx in range(COUNT):
            if self.__CheckAbort():
                return False
        
            self.__progressHandler.Step()
            image1 = self.__aRenderer.ProcessCropAndResize(imgFrom,
                                                           pathRectsFrom[idx], 
                                                           self.__profile.PResolution)

            self.__progressHandler.Step()
            image2 = self.__aRenderer.ProcessCropAndResize(imgTo,
                                                           pathRectsTo[idx], 
                                                           self.__profile.PResolution)

            img = Image.blend(image1, image2, idx / float(COUNT))
#            img = self.roll(image1, image2, idx / float(COUNT))
            
            self.__aRenderer.ProcessFinalize(img)
        
        return True

    def roll(self, img1, img2, proc):
        xsize, ysize = img1.size
        delta = int(xsize * proc)
        part1 = img2.crop((0, 0, delta, ysize))
        part2 = img1.crop((delta, 0, xsize, ysize))
        image = img2.copy()
        image.paste(part2, (0, 0, xsize-delta, ysize))
        image.paste(part1, (xsize-delta, 0, xsize, ysize))
        return image
    
    def __Start(self, pics):
        self.__progressHandler.SetInfo(_(u"initialize renderer"))
        self.__aRenderer.Prepare()
        
        TRANS_COUNT = self.__GetTransCount()

        pathRectsBefore = None
        pathRectsCurrent = None
        
        imgBefore = None
        imgCurrent = None
        
        for idxPic, pic in enumerate(pics):
            infoText = _(u"processing image %d/%d") % (idxPic, len(pics))
            self.__progressHandler.SetInfo(infoText)

            imgCurrent = pic.GetImage()
            pathRectsCurrent = self.__ComputePath(pic)

            if idxPic > 0:
                if idxPic == 1:
                    phase1 = pathRectsBefore[:-TRANS_COUNT]
                    if not self.__ProcAndFinal(imgBefore, phase1):
                        return
                
                infoText = _(u"processing transition %d/%d") % (idxPic, len(pics))
                self.__progressHandler.SetInfo(infoText)
                
                phase2a = pathRectsBefore[-TRANS_COUNT:]
                phase2b = pathRectsCurrent[:TRANS_COUNT]
                if not self.__TransAndFinal(imgBefore, imgCurrent, 
                                            phase2a, phase2b):
                    return
                
                infoText = _(u"processing image %d/%d") % (idxPic+1, len(pics))
                self.__progressHandler.SetInfo(infoText)

                phase3 = pathRectsCurrent[TRANS_COUNT:-TRANS_COUNT]
                if not self.__ProcAndFinal(imgCurrent, phase3):
                    return
                
                if idxPic == len(pics) - 1:
                    phase4 = pathRectsCurrent[-TRANS_COUNT:]
                    if not self.__ProcAndFinal(imgCurrent, phase4):
                        return

            imgBefore = imgCurrent
            pathRectsBefore = pathRectsCurrent

                    
        if self.__audioFile:
            self.__progressHandler.SetInfo(_(u"processing audiofile..."))
            self.__aRenderer.ProcessAudio(self.__audioFile)
            self.__progressHandler.Steps(5)
        
        self.__progressHandler.SetInfo(_(u"creating output..."))
        self.__aRenderer.Finalize()
        
    def SetAudioFile(self, audioFile):
        self.__audioFile = audioFile
    
    def Start(self, pics, targetLengthSecs=None):
        generateSubtitle = False
        
        if targetLengthSecs is not None:
            targetLengthSecs = max(targetLengthSecs - self.__transDuration, len(pics))
            totalSecs = 0
            for pic in pics:
                totalSecs += pic.GetDuration()
            self.__picCountFactor = targetLengthSecs / totalSecs
            
        count = 0
        for pic in pics:
            count += int(self.__GetPicCount(pic))
            
            if pic.GetComment() and not generateSubtitle:
                generateSubtitle = True
                count += 1

        if self.__audioFile:
            count += 5
        
        self.__progressHandler.SetMaxProgress(int(count))
        
        try:
            if generateSubtitle:
                self.__progressHandler.SetInfo(_(u"generating subtitle"))
                st = SubtitleSrt(self.__aRenderer.POutputPath, self.__picCountFactor)
                st.Start(pics)
                self.__progressHandler.Step()
            
            self.__Start(pics)
            return True
        except StandardError, err:
            import traceback
            traceback.print_exc()
            self.__errorMsg = "%s: %s" % (err.__class__.__name__, err.message)
            return False
        finally:
            self.__progressHandler.Done()

    def GetErrorMessage(self):
        return self.__errorMsg
