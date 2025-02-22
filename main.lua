ShortCharacterIntroMod = RegisterMod("Short Character Intro", 1)
local mod = ShortCharacterIntroMod

------ Mod Config Menu ------
local json = require("json")

mod.config = {
    toggleKey = Keyboard.KEY_HOME,
}

if ModConfigMenu then
    ModConfigMenu.AddSetting("Short Character Intro", nil,
        {
            Type = ModConfigMenu.OptionType.KEYBIND_KEYBOARD,
            CurrentSetting = function()
                return mod.config.toggleKey
            end,
            Display = function()
                local key = "None"
                if (InputHelper.KeyboardToString[mod.config.toggleKey]) then
                    key = InputHelper.KeyboardToString[mod.config.toggleKey]
                end
                return "Toggle Key: " .. key
            end,
            OnChange = function(currentNum)
                mod.config.toggleKey = currentNum or -1
            end,
            PopupGfx = ModConfigMenu.PopupGfx.WIDE_SMALL,
            PopupWidth = 280,
            Popup = function()
                local currentValue = mod.config.toggleKey
                local keepSettingString = ""
                if currentValue > -1 then
                    local currentSettingString = InputHelper.KeyboardToString[currentValue]
                    keepSettingString = 'Current key: "' .. currentSettingString .. 
                        '".$newlinePress this key again to keep it.$newline$newline'
                end
                return "Press any key to set as toggle key.$newline$newline" ..
                    keepSettingString .. "Press ESCAPE to clear this setting."
            end,
            Info = "Set the key to call the intro animation."
        }
    )
end

mod:AddPriorityCallback(
    ModCallbacks.MC_POST_GAME_STARTED, CallbackPriority.IMPORTANT,
    ---@param isContinued boolean
    function(_, isContinued)
        if not mod:HasData() then
            return
        end

        local jsonString = mod:LoadData()
        mod.config = json.decode(jsonString)
        mod.config.toggleKey = mod.config.toggleKey or Keyboard.KEY_HOME
    end
)

mod:AddPriorityCallback(
    ModCallbacks.MC_PRE_GAME_EXIT, CallbackPriority.LATE,
    function(shouldSave)
        local jsonString = json.encode(mod.config)
        mod:SaveData(jsonString)
    end
)


------ 스프라이트 로드 & 정리 ------
local sprite = Sprite()
sprite:Load("Short Character Intro/popup_characterdescriptions.anm2")

local function GetScreenSize()
    local room = Game():GetRoom()
    local pos = room:WorldToScreenPosition(Vector(0,0)) - room:GetRenderScrollOffset() - Game().ScreenShakeOffset
    local rx = pos.X + 60 * 26 / 40
    local ry = pos.Y + 162.5 * (26 / 40)
    return Vector(rx*2 + 13*26, ry*2 + 7*26)
end


------ 구현 ------
mod.currentAnim = nil      -- 현재 재생중인 애니메이션 이름
mod.isAnimating = false    -- 애니메이션이 재생 중인지
mod.showIn = true          -- 토글 상태: true면 다음은 인 애니메이션, false면 아웃 애니메이션

mod:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    if mod.currentAnim then
        if not sprite:IsFinished(mod.currentAnim) then    -- 애니메이션이 아직 끝나지 않았다면 업데이트
            sprite:Update()
        else
            mod.isAnimating = false
        end

        if Options.MaxScale == 1 or Options.MaxScale == 2 then
            sprite.Scale = Vector(0.5, 0.5)
        elseif Options.MaxScale == 3 then
            sprite.Scale = Vector(0.666666, 0.666666)
        else
            sprite.Scale = Vector(0.75, 0.75)
        end
        
        sprite.Color = Color(1, 1, 1, 1, 0, 0, 0)
        sprite:Render(Vector(GetScreenSize().X/2, GetScreenSize().Y/3.333333), Vector(0,0), Vector(0,0))
    end
end)

mod:AddCallback(ModCallbacks.MC_POST_PLAYER_UPDATE, function(_, player)
    if Input.IsButtonTriggered(mod.config.toggleKey, 0) then
        if mod.isAnimating then return end    -- 만약 애니메이션이 재생 중이면 새 입력은 무시

        local playerType = player:GetPlayerType()
        if mod.showIn then
            mod.currentAnim = playerType .. "_In"
            mod.playsfx = 17
        else
            mod.currentAnim = playerType .. "_Out"
            mod.playsfx = 18
        end

        sprite:Play(mod.currentAnim, false)
        SFXManager():Play(mod.playsfx, 0.5)
        mod.isAnimating = true

        mod.showIn = not mod.showIn
    end
end)
